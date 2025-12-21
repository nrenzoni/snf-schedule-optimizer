import whenever

from snf_schedule_optimizer.ml_output_retrievers import IMLModelOutputsRetriever

# Import Models
from snf_schedule_optimizer.models import (
    Employee,
    EmployeeTimeSettings,
    HprdEnforcedRole,
    LookbackPeriod,
    MealDeductionRules,
    MlModelOutputs,
    NurseProfile,
    PreferenceWeights,
    PunchType,
    RoundingType,
    Shift,
    ShiftKey,
    ShiftSpecificRequirements,
    SplitDayType,
    StaffCompensationRecord,
    WorkedShiftSegment,
)
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    HprdShiftNurseRequirementHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import IHprdRequirementCalculator

# Import your Interfaces
from snf_schedule_optimizer.persistence.nurse_retrievers import INurseRetriever
from snf_schedule_optimizer.services.hr.interfaces import (
    IEmployeeRetriever,
    IStaffCompensationRetriever,
)
from snf_schedule_optimizer.services.payroll.calculations.overtime_calculation import (
    ThresholdOvertimeRule,
)
from snf_schedule_optimizer.services.payroll.interfaces import IFacilityRulesService
from snf_schedule_optimizer.services.scheduling.interfaces import (
    IPreferencePenaltyProcessor,
    IShiftRequirementsRetriever,
)
from snf_schedule_optimizer.services.timekeeping.interfaces import (
    IEmployeeWorkHistoryService,
)
from snf_schedule_optimizer.utils.time_utils import TimeRoundingUtility


class FakeEmployeeRetriever(IEmployeeRetriever):
    def __init__(self, employees: list[Employee]):
        self._employees = employees

    async def get_all_employees(
        self,
        org_id: str,
    ) -> list[Employee]:
        return self._employees

    async def get_employee_by_id(
        self,
        org_id: str,
        employee_id: str,
    ) -> Employee | None:
        return next((e for e in self._employees if e.employee_id == employee_id), None)


class FakeNurseRetriever(INurseRetriever):
    def __init__(self, nurses: list[NurseProfile]):
        self._nurses = nurses

    async def get_nurses(self, shift: Shift) -> list[NurseProfile]:
        # Simple Fake: Returns all configured nurses regardless of shift
        # You could add filtering logic here if you wanted smarter tests
        return self._nurses

    async def get_nurse(self, employee_id: str) -> NurseProfile | None:
        return next((n for n in self._nurses if n.employee_id == employee_id), None)


class FakeStaffCompensationRetriever(IStaffCompensationRetriever):
    def __init__(self, records: list[StaffCompensationRecord]):
        self._records = records
        self.tz = "America/New_York"

    async def get_record_for_date(
        self,
        employee_id: str,
        date: whenever.ZonedDateTime,
    ) -> StaffCompensationRecord | None:
        # Simple Fake: finds the record matching ID.
        # (Ignores date logic for simplicity, or implement strict logic if needed)
        return next((r for r in self._records if r.employee_id == employee_id), None)

    async def get_base_rate(self, employee_id: str) -> float:
        # Fallback method if used
        rec = await self.get_record_for_date(
            employee_id,
            whenever.Instant.now().to_tz(self.tz),
        )
        return rec.base_rate_effective if rec else 0.0

    def get_hours_worked_in_period(self, employee_id: str) -> float:
        return 0.0


class FakeWorkHistoryService(IEmployeeWorkHistoryService):
    def __init__(self, accumulated_hours_map: dict[str, float]):
        self._hours_map = accumulated_hours_map

    async def get_processed_history_for_period(
        self,
        org_id: str,
        employee_id: str,
        check_date: whenever.Instant,
        facility_id: str | None = None,
    ) -> dict[ShiftKey, list[WorkedShiftSegment]]:
        # We don't need to return complex segments if we override the provider logic,
        # but to satisfy the type checker:
        return {}

    async def get_remaining_non_ot_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        ot_rules: list[ThresholdOvertimeRule],
    ) -> dict[LookbackPeriod, float]:
        raise NotImplementedError()

    async def get_accumulated_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        history: dict[ShiftKey, list[WorkedShiftSegment]],
        threshold_hours: float,
        lookback_period: LookbackPeriod,
        work_period_start_day: whenever.Weekday | None = None,
        work_period_start_time: whenever.Time | None = None,
    ) -> float:
        return self._hours_map.get(employee.employee_id, 0.0)

    def get_consecutive_days_worked(
        self,
        employee: Employee,
        current_shift: Shift,
        history: dict[Shift, list[WorkedShiftSegment]],
        max_consecutive_days: int,
    ) -> list[whenever.Date]:
        return []


class FakeMLModelRetriever(IMLModelOutputsRetriever):
    def __init__(self, default_model_outputs: MlModelOutputs):
        self.default_model_outputs = default_model_outputs

    def get_model_outputs(self, shift: Shift) -> MlModelOutputs:
        return self.default_model_outputs


class FakePreferencePenaltyProcessor(IPreferencePenaltyProcessor):
    def __init__(self, penalty_map: dict[str, float] | None = None):
        """
        Args:
            penalty_map: A dictionary mapping "employee_id:shift_id" -> float penalty cost.
        """
        self._penalty_map = penalty_map or {}

    async def calculate_penalty_cost(
        self,
        employee: Employee,
        nurse: NurseProfile,
        shift: Shift,
        weights: PreferenceWeights,
    ) -> float:
        # Construct a simple composite key to lookup the pre-configured penalty
        key = f"{employee.employee_id}:{shift.shift_id}"

        # Return the configured float, or 0.0 to safely allow addition
        return self._penalty_map.get(key, 0.0)


class FakeShiftRequirementsRetriever(IShiftRequirementsRetriever):
    def __init__(
        self,
        requirements_map: dict[str, ShiftSpecificRequirements] | None = None,
        default_requirements: ShiftSpecificRequirements | None = None,
    ):
        """
        Args:
            requirements_map: Map of shift_id -> specific requirements.
            default_requirements: Returned if shift_id is not in the map.
        """
        self._map = requirements_map or {}
        # Create a zeroed-out default if none provided (mimics your previous MagicMock 0.0 behavior)
        self._default = default_requirements or ShiftSpecificRequirements(
            target_hprd_rn=0.0, target_hprd_cna=0.0, target_total_hprd=0.0
        )

    async def get_shift_requirements(
        self, shift: Shift
    ) -> ShiftSpecificRequirements | None:
        return self._map.get(shift.shift_id, self._default)


class FakeHprdRequirementCalculator(IHprdRequirementCalculator):
    def __init__(
        self, requirements_map: dict[tuple[str, HprdEnforcedRole], float] | None = None
    ):
        """
        Args:
            requirements_map: Dictionary mapping (shift_id, Role) -> required_count (float)
        """
        self._map = requirements_map or {}

    async def calculate_requirements(
        self, context: FacilityScenarioContext
    ) -> HprdShiftNurseRequirementHolder:
        # 1. Create the REAL holder data structure
        holder = HprdShiftNurseRequirementHolder(
            [s.shift_id for s in context.shifts],
            [HprdEnforcedRole.RN, HprdEnforcedRole.CNA],
        )

        # 2. Populate it with our test data
        for (shift_id, role), count in self._map.items():
            # Only set if the shift is actually part of this optimization run
            if shift_id in holder.shifts:
                holder[shift_id, role] = count

        return holder


class FacilityRulesServiceStaticListImpl(IFacilityRulesService):
    """
    Concrete implementation providing static, hardcoded payroll rules for testing
    the Shift Reconciler and other services.
    """

    def __init__(self) -> None:
        # Hardcode the essential parameters for internal use
        self.DEFAULT_ROUNDING_UNIT = 6
        self.DEFAULT_PAIRING_THRESHOLD = whenever.DateTimeDelta(hours=10)
        self.DEFAULT_SPLIT_TIME = whenever.Time(3, 0, 0)
        self.DEFAULT_GRACE_WINDOW = whenever.DateTimeDelta(minutes=15)

        # Instantiate the deduction rules once
        self.default_meal_rules = MealDeductionRules(
            meal_threshold_hours=6.0,
            meal_duration_hours=0.5,  # 30 minutes
            is_mandatory=True,
        )

    async def apply_rounding(
        self,
        org_id: str,
        raw_time: whenever.ZonedDateTime,
        punch_type: PunchType,
    ) -> whenever.ZonedDateTime:
        """
        Applies a standard nearest-interval rounding (e.g., 6-minute rule).
        """
        return TimeRoundingUtility.round_to_nearest_unit(
            raw_time,
            self.DEFAULT_ROUNDING_UNIT,
        )

    async def get_time_settings(
        self,
        org_id: str,
        employee_id: str,
        facility_id: str,
        check_dt: whenever.ZonedDateTime,
    ) -> EmployeeTimeSettings:
        """
        Retrieves hardcoded time settings, ignoring employee_id and date for simplicity.
        """
        # In production, this would filter by union contract/facility rules active on check_dt.
        return EmployeeTimeSettings(
            pairing_threshold=self.DEFAULT_PAIRING_THRESHOLD,
            split_day_threshold_time=self.DEFAULT_SPLIT_TIME,
            shift_separator_time=self.DEFAULT_SPLIT_TIME,  # Using the split time as separator for simplicity
            shift_grace_window=self.DEFAULT_GRACE_WINDOW,
            rounding_unit_minutes=self.DEFAULT_ROUNDING_UNIT,
            split_day_day_type=SplitDayType.CURRENT,
            rounding_type=RoundingType.NEAREST,
        )

    async def get_meal_deduction_rules(
        self,
        org_id: str,
        facility_id: str,
        check_dt: whenever.ZonedDateTime,
    ) -> MealDeductionRules | None:
        """
        Retrieves the standard 6-hour threshold/30-minute mandatory deduction rules.
        """
        # In production, this would check state/federal laws and return the applicable rule.
        return self.default_meal_rules
