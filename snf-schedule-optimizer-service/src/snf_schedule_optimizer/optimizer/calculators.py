import whenever

from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IShiftRequirementsRepo,
)
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    NurseProfile,
    PreferenceType,
    Shift,
    ShiftSpecificRequirements,
)
from snf_schedule_optimizer.optimizer.clocks import IClock
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    HprdShiftNurseRequirementHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import (
    IHprdRequirementCalculator,
    IIncentiveManager,
    ILaborBurdenCalculator,
    INurseHardBlockChecker,
)
from snf_schedule_optimizer.resident_acuity_repo import (
    IResidentAcuityPerShiftRepo,
)


class HprdRequirementCalculator(IHprdRequirementCalculator):
    """
    Calculates staffing requirements by merging facility budgets
    with shift-specific overrides and census data.
    """

    def __init__(
        self,
        resident_acuity_retriever: IResidentAcuityPerShiftRepo,
        shift_requirements_retriever: IShiftRequirementsRepo,
    ):
        self.resident_acuity_retriever = resident_acuity_retriever
        self.shift_requirements_retriever = shift_requirements_retriever

    async def calculate_requirements(
        self, context: FacilityScenarioContext
    ) -> HprdShiftNurseRequirementHolder:
        # 1. Initialize result holder
        hprd_shift_nurse_requirements = HprdShiftNurseRequirementHolder(
            [s.shift_id for s in context.shifts],
            [HprdEnforcedRole.RN, HprdEnforcedRole.CNA],
        )

        if context.min_mandates is None:
            raise ValueError(
                f"Cannot calculate HPRD requirements for facility {context.facility_id}: "
                "MinMandates is missing from context."
            )

        # 2. Iterate through shifts and resolve requirements
        for shift in context.shifts:
            # Step A: Resolve Staffing Targets (Hierarchy: Override -> Facility Default)
            targets = await self._resolve_staffing_targets(shift, context.config)

            # Step B: Get Census/Acuity
            # Census is the primary driver of labor demand in SNFs.
            residents_acuity = (
                await self.resident_acuity_retriever.get_resident_acuity_list(shift)
            )
            shift_census = len(residents_acuity)

            hours_in_shift = shift.duration_hours
            if hours_in_shift <= 0:
                continue

            # Step C: Calculate Required Headcount
            # Demand = (Target HPRD * Census) / Shift Duration
            # Example: (0.5 RN_HPRD * 100 Residents) / 8 Hours = 6.25 RNs required
            required_rn_hours = targets.target_hprd_rn * shift_census
            required_cna_hours = targets.target_hprd_cna * shift_census
            required_total_hours = targets.target_total_hprd * shift_census

            # Step D: Apply "Bodies on the Floor" Minimums (Min Mandates)
            # We never schedule fewer than the mandated minimum, even if HPRD math allows it.
            req_rn_count = max(
                (required_rn_hours / hours_in_shift),
                float(context.min_mandates.min_staff_per_shift_rn),
            )

            req_cna_count = max(
                (required_cna_hours / hours_in_shift),
                float(context.min_mandates.min_staff_per_shift_cna),
            )

            # Step E: Commit to Requirements Holder for the Solver
            hprd_shift_nurse_requirements[shift.shift_id, HprdEnforcedRole.RN] = (
                req_rn_count
            )
            hprd_shift_nurse_requirements[shift.shift_id, HprdEnforcedRole.CNA] = (
                req_cna_count
            )

            # Add total constraint (used by the enterprise solver for global budget balancing)
            hprd_shift_nurse_requirements.add_total_req(
                shift, required_total_hours / hours_in_shift
            )

        return hprd_shift_nurse_requirements

    async def _resolve_staffing_targets(
        self, shift: Shift, facility_config: FacilityConfig
    ) -> ShiftSpecificRequirements:
        """
        Internal logic to resolve the staffing target hierarchy.
        Provides a robust fallback mechanism to the facility baseline.
        """
        # Level 1: Check for Shift-Specific Override in DB (e.g., high acuity surge)
        override = await self.shift_requirements_retriever.get_shift_requirements(shift)

        if override:
            return override

        # Level 2: Fallback to Facility Baseline (Budget)
        return ShiftSpecificRequirements(
            target_hprd_rn=facility_config.default_hprd_rn,
            target_hprd_cna=facility_config.default_hprd_cna,
            target_total_hprd=facility_config.default_hprd_total,
        )


class NurseHardBlockCheckerImpl(INurseHardBlockChecker):
    def check(self, nurse: NurseProfile, shift: Shift) -> bool:
        # Check 1: Mandatory time off blocks (from StaffPreference)
        if nurse.shift_custom_preferences:
            for pref in nurse.shift_custom_preferences:
                if pref.is_hard_block:
                    if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                        # FIX: The specific_value must be converted to WeekDay for comparison.
                        # Assuming specific_value is stored as an integer (0-6) or a string representation of the integer.
                        try:
                            # Safely convert to int, then to WeekDay if needed, or compare int to WeekDay.value
                            pref_day_int = (
                                int(pref.specific_value)
                                if pref.specific_value is not None
                                else -1
                            )
                        except ValueError:
                            pref_day_int = -1  # Invalid value means no match

                        if shift.day_of_week.value == pref_day_int:
                            return True
                    elif pref.preference_type == PreferenceType.WEEKEND_OFF:
                        if shift.day_of_week in {
                            whenever.Weekday.SATURDAY,
                            whenever.Weekday.SUNDAY,
                        }:
                            return True
        return False

        # Check 2: Max weekly/monthly hour limits (Fatigue/Compliance)
        # This is complex in LP, usually handled via SUM constraints, but included here for logic completeness

        # Check 3: Role/Skill match (RN cannot cover CNA shift if hard rule)
        # if self.config.unit_needs_rn(day_shift) and nurse.role != 'RN':
        #    return False


class StandardLaborBurdenCalculator(ILaborBurdenCalculator):
    def __init__(self) -> None:
        # Configuration could actually come from a DB
        self.fica_rate = 0.0765  # 6.2% SS + 1.45% Medicare
        self.futa_sui_rate = 0.03  # Estimate for Unemployment
        self.work_comp_rate = 0.02  # Estimate for Nursing

        # Benefits: Usually calculated as a fixed $ per hour or % of wage
        self.benefits_load_factor = 0.15  # 15% for Health/401k/PTO

    def calculate_burden(
        self,
        employee: Employee,
        base_cost: float,
    ) -> tuple[float, float]:
        # 1. Statutory Taxes (FICA, etc.) are strictly % of wage
        statutory = base_cost * (
            self.fica_rate + self.futa_sui_rate + self.work_comp_rate
        )

        # 2. Benefits
        # In refined models, checking employee.enrollment_status is better.
        # For optimization, a load factor is standard.
        benefits = base_cost * self.benefits_load_factor

        return statutory, benefits


class ConfigurableIncentiveManager(IIncentiveManager):
    def __init__(
        self,
        holidays: set[whenever.Date],
        urgency_threshold_days: int,
        pickup_bonus: float,
        clock: IClock,
    ):
        self.holidays = holidays
        self.urgency_threshold_days = urgency_threshold_days  # e.g., 2 days
        self.pickup_bonus_amount = pickup_bonus  # e.g., $50 flat
        self.clock = clock

    def calculate_incentives(
        self,
        shift: Shift,
        employee: Employee,
        base_rate: float,
    ) -> float:
        total_incentive = 0.0

        # 1. Holiday Logic
        # If shift starts on a holiday
        if shift.shift_start_dt.date() in self.holidays:
            # Usually 1.5x Base Rate.
            # Note: We return the *Incremental* cost here.
            # Base is already paid. We add the 0.5x premium.
            total_incentive += base_rate * 0.5 * shift.duration_hours

        # 2. Urgent "Pick-up" Bonus
        # If scheduling for "Tomorrow", add bonus cost

        now_instant = self.clock.now()
        now_local = now_instant.to_tz(shift.shift_start_dt.tz)

        shift_date = shift.shift_start_dt.date()
        today_date = now_local.date()

        delta = shift_date - today_date
        days_until_shift = delta.in_months_days()[1]

        if 0 <= days_until_shift <= self.urgency_threshold_days:
            total_incentive += self.pickup_bonus_amount

        # 3. Amortized Bonuses (Sunk Cost?)
        # Optimization Theory Note: Strictly speaking, a sign-on bonus is a "Sunk Cost"
        # and shouldn't affect the decision to schedule a shift today.
        # However, if you want "Total Budget Accuracy", you include it.
        # total_incentive += employee.daily_amortized_bonus

        return total_incentive
