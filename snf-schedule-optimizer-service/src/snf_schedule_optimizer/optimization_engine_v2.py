import abc
import enum
from collections import defaultdict
from dataclasses import dataclass
import pendulum

import numpy as np
import pulp
from pulp import LpMinimize, LpProblem, LpVariable

from snf_schedule_optimizer.models import *
from snf_schedule_optimizer.datetime_utils import is_weekend
from snf_schedule_optimizer.ml_output_retrievers import IMLModelOutputsRetriever
from snf_schedule_optimizer.persistence.nurse_retrievers import INurseRetriever
from snf_schedule_optimizer.resident_acuity_retrievers import (
    IResidentAcuityPerShiftRetriever,
)
from snf_schedule_optimizer.services.hr.interfaces import (
    IEmployeeRetriever,
    IStaffCompensationService,
)
from snf_schedule_optimizer.services.scheduling.interfaces import (
    IPreferencePenaltyProcessor,
    IShiftRequirementsRetriever,
)
from snf_schedule_optimizer.services.timekeeping.interfaces import (
    IEmployeeWorkHistoryService,
)


class OvertimeRuleType(enum.StrEnum):
    WEEKLY_VOLUME = "WEEKLY_VOLUME"  # Classic > 40 hours
    CALIFORNIA_DAILY = "CALIFORNIA_DAILY"  # > 8 hours in a day is OT
    CONSECUTIVE_DAYS = "CONSECUTIVE_DAYS"  # > N days in a row is OT


@dataclass(frozen=True)
class OvertimeConfig:
    rule_type: OvertimeRuleType
    threshold: float  # e.g., 40.0 for weekly, 8.0 for daily, 6.0 for consecutive
    ot_multiplier: float = 1.5


@dataclass(frozen=True)
class ShiftCostBreakdown:
    base_wage: float  # Hourly Rate * Hours
    overtime_premium: float  # The extra 0.5x portion
    statutory_burden: float  # Taxes (FICA, SUI, FUTA)
    benefits_burden: float  # Health, 401k, PTO Accrual
    shift_differentials: float  # NOC, Weekend
    incentive_bonuses: float  # Pick-up, Holiday, Sign-on

    @property
    def total_optimization_cost(self) -> float:
        """The single number the solver uses to minimize cost."""
        return (
            self.base_wage
            + self.overtime_premium
            + self.statutory_burden
            + self.benefits_burden
            + self.shift_differentials
            + self.incentive_bonuses
        )


@dataclass(frozen=True)
class ScheduleOptimizationParams:
    pass


class InfeasibilityReason(enum.StrEnum):
    NO_AVAILABLE_NURSES = (
        "No available nurses to cover required role"  # includes hard blocks
    )
    OTHER = "Other infeasibility reason"


@dataclass(frozen=True)
class InfeasibilityReasonResult:
    reason: InfeasibilityReason
    details: Optional[str] = None


@dataclass(frozen=True)
class ScheduleOptimizationResults:
    success: bool
    optimal_schedule: Optional[Schedule]
    constraint_slacks: Optional[Dict[str, float]]
    infeasibility_reason: Optional[InfeasibilityReasonResult]


@dataclass
class OptimizationContext:
    """
    Holds transient data calculated during the optimization lifecycle,
    shared between different strategies.
    """

    shifts: List[Shift]
    facility_config: FacilityConfig
    # ... other configs ...
    all_employees: List[Employee]  # Pre-fetched list

    # Data calculated in Phase 1 (Pre-calculation)
    hprd_requirements: Optional["HprdShiftNurseRequirementHolder"] = None
    # Potentially pre-calculated financial data, unavailable staff lists, etc.


class LpNurseShiftVariableHolder:
    def __init__(self) -> None:
        self.variables: Dict[str, LpVariable] = {}
        # Stores: employee_id -> {'reg': Var, 'ot': Var}
        self.pay_variables: Dict[str, Dict[str, LpVariable]] = {}

    def add_variable(
        self,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable:
        var_name = f"X__{employee_id}__{shift_id}"
        var = LpVariable(var_name, cat=pulp.LpBinary)
        self.variables[var_name] = var
        return var

    def get_variable(
        self,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable:
        return self.variables[f"X__{employee_id}__{shift_id}"]

    def add_pay_variables(
        self,
        employee_id: str,
    ) -> None:
        """Creates the bucket variables for Volume-based OT."""
        self.pay_variables[employee_id] = {
            "reg": LpVariable(
                f"H_Reg__{employee_id}", lowBound=0, cat=pulp.LpContinuous
            ),
            "ot": LpVariable(f"H_OT__{employee_id}", lowBound=0, cat=pulp.LpContinuous),
        }

    def get_pay_variables(
        self,
        employee_id: str,
    ) -> Optional[Dict[str, LpVariable]]:
        return self.pay_variables.get(employee_id)


class INurseHardBlockChecker(abc.ABC):
    """
    Checks if the nurse has any hard block preferences for the given shift.
    """

    @abc.abstractmethod
    def check(
        self,
        nurse: NurseProfile,
        shift: Shift,
    ) -> bool:
        """
        Checks all HARD BLOCKERS (time off requests, skill gaps, max hours).
        :return: True if the nurse cannot be assigned to this shift due to hard blocks.
        """
        pass


class IIncentiveManager(abc.ABC):
    @abc.abstractmethod
    def calculate_incentives(
        self,
        shift: Shift,
        employee: Employee,
        base_rate: float,
    ) -> float:
        pass


class IPayModelStrategy(abc.ABC):
    """
    Encapsulates HOW we pay people.
    Examples:
    - WeeklyOvertimeStrategy (Uses Buckets)
    - DailyOvertimeStrategy (Uses Shift Coefficients)
    - ExemptSalaryStrategy (Fixed cost)
    """

    @abc.abstractmethod
    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        """Initialize buckets (h_reg, h_ot) if needed."""
        pass

    @abc.abstractmethod
    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        """Apply math: sum(shifts) == reg + ot, or similar."""
        pass

    @abc.abstractmethod
    def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> List[pulp.LpAffineExpression]:
        """Return the cost expression (e.g., h_reg * 20 + h_ot * 30)."""
        pass


class ILaborBurdenCalculator(abc.ABC):
    @abc.abstractmethod
    def calculate_burden(
        self, employee: Employee, base_cost: float
    ) -> Tuple[float, float]:
        """Returns (statutory_burden, benefits_burden)"""
        pass


class IRuleConstraintStrategy(abc.ABC):
    """
    Encapsulates HARD constraints.
    Examples:
    - MinHprdStrategy (Regulatory compliance)
    - UnionFatigueStrategy (Max consecutive days)
    - SkillMixStrategy (Must have 1 RN on floor)
    """

    @abc.abstractmethod
    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> Optional[InfeasibilityReasonResult]:
        """
        Applies constraints directly to the 'problem'.
        Returns a reason if immediate infeasibility is detected (optional).
        """
        pass


class IObjectivePenaltyStrategy(abc.ABC):
    """
    Encapsulates SOFT preferences.
    Examples:
    - NursePreferenceStrategy (Day vs Night)
    - ContinuityStrategy (Keep same staff on same hall)
    - TurnoverRiskStrategy (Don't burnout high-risk staff)
    """

    @abc.abstractmethod
    def get_penalty_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
        weights: PreferenceWeights,
    ) -> List[Any]:
        """
        Returns a list of LpAffineExpression terms to be ADDED to the objective function.
        E.g. [ (x_1 * 50), (x_2 * 100) ]
        """
        pass


class IHprdRequirementCalculator(abc.ABC):
    @abc.abstractmethod
    def calculate_requirements(
        self,
        shifts: List[Shift],
        config: FacilityConfig,
        min_mandate: MinMandates,
    ) -> "HprdShiftNurseRequirementHolder":
        pass


class HprdShiftNurseRequirementHolder:
    """
    Stores the required HPRD-adjusted nurse hours per shift and role.
    """

    def __init__(
        self,
        shifts: List[str],  # shift_ids
        roles: List[HprdEnforcedRole],
    ):
        # self.values: np.ndarray[Any, np.dtype[np.float64]]  # Shape: (n_shifts, n_roles)
        self.values = np.zeros((len(shifts), len(roles) + 1))

        self.shifts = shifts  # shift_ids
        self.roles = roles

    def __setitem__(
        self,
        key: Tuple[str, HprdEnforcedRole],
        value: float,
    ) -> None:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        self.values[shift_idx, role_idx] = value

    def __getitem__(
        self, key: Tuple[str, HprdEnforcedRole]
    ) -> float:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        return float(self.values[shift_idx, role_idx])

    def add_total_req(self, shift: Shift, value: float) -> None:
        shift_idx = self.shifts.index(shift.shift_id)
        self.values[shift_idx, -1] += value

    def get_total_req(self, shift_str: str) -> float:
        shift_idx = self.shifts.index(shift_str)
        return float(self.values[shift_idx, -1])


class HprdStaffingConstraintStrategy(IRuleConstraintStrategy):
    def __init__(
        self,
        hard_block_checker: INurseHardBlockChecker,
    ):
        self.hard_block_checker = hard_block_checker

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> Optional[InfeasibilityReasonResult]:
        # todo: Add infeasibility checks (e.g., no available nurses for a required role)

        requirements_holder = data_provider.get_hprd_requirements()
        shifts = data_provider.get_shifts()

        # "For every shift, sum of assigned nurses >= Required HPRD count"
        for shift in shifts:
            # Get requirements (e.g., {RN: 2.5, CNA: 10.0})
            # This assumes your HPRD holder logic is accessible or pre-calculated
            # For simplicity, let's assume we iterate roles:
            for role in [HprdEnforcedRole.RN, HprdEnforcedRole.CNA]:
                required_count = requirements_holder[shift.shift_id, role]

                if required_count <= 0:
                    continue

                available_vars = []
                nurses = data_provider.get_nurses_for_shift(shift)

                for nurse in nurses:
                    # Filter by Hard Blocks (Time off, etc.)
                    # Note: We enforce blocks by NOT adding the variable to the sum,
                    # OR by explicitly adding x = 0 constraint.
                    # Explicit constraint is safer for transparency.
                    lp_var = lp_holder.get_variable(nurse.employee_id, shift.shift_id)

                    if self.hard_block_checker.check(nurse, shift):
                        # HARD BLOCK: Force variable to 0
                        problem += (
                            lp_var == 0,
                            f"HardBlock_{nurse.employee_id}_{shift.shift_id}",
                        )
                        continue

                    # Filter by Role
                    employee = data_provider.get_employee_by_id(nurse.employee_id)
                    if not employee:
                        continue  # todo: should this be an error?

                    if employee.job_title != role.value:
                        continue

                    # Available: Add to the pool
                    available_vars.append(lp_var)

                # Add the HPRD Sum Constraint
                problem += (
                    pulp.lpSum(available_vars) >= required_count,
                    f"MinStaff_{shift.shift_id}_{role.value}",
                )

        return None


class ConsecutiveShiftFatigueStrategy(IRuleConstraintStrategy):
    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> Optional[InfeasibilityReasonResult]:
        shifts = data_provider.get_shifts()

        # todo: Make this more generic/configurable, add infeasibility checks

        # Simple example: Cannot work Shift 1 AND Shift 2 if they overlap or are back-to-back
        # (You can inject a specific logic class here if it gets complex)
        for i in range(len(shifts) - 1):
            s1, s2 = shifts[i], shifts[i + 1]
            # Simple check: if < 8 hours gap
            gap = (s2.shift_start_dt - s1.shift_end_dt).total_hours()
            if gap < 8.0:
                # Find common nurses
                nurses_s1 = {
                    n.employee_id for n in data_provider.get_nurses_for_shift(s1)
                }
                nurses_s2 = {
                    n.employee_id for n in data_provider.get_nurses_for_shift(s2)
                }
                common = nurses_s1.intersection(nurses_s2)

                for emp_id in common:
                    v1 = lp_holder.get_variable(emp_id, s1.shift_id)
                    v2 = lp_holder.get_variable(emp_id, s2.shift_id)
                    problem += v1 + v2 <= 1, f"Fatigue_{emp_id}_{s1.shift_id}"

        return None


class HprdRequirementCalculatorImpl(IHprdRequirementCalculator):
    def __init__(
        self,
        resident_acuity_retriever: IResidentAcuityPerShiftRetriever,
        shift_requirements_retriever: IShiftRequirementsRetriever,
    ):
        self.resident_acuity_retriever = resident_acuity_retriever
        self.shift_requirements_retriever = shift_requirements_retriever

    def calculate_requirements(
        self,
        shifts: List[Shift],
        config: FacilityConfig,
        min_mandate: MinMandates,
    ) -> HprdShiftNurseRequirementHolder:
        # --- YOUR ORIGINAL LOGIC GOES HERE ---

        hprd_shift_nurse_requirements = HprdShiftNurseRequirementHolder(
            [s.shift_id for s in shifts], [HprdEnforcedRole.RN, HprdEnforcedRole.CNA]
        )

        for shift in shifts:
            shift_requirements = (
                self.shift_requirements_retriever.get_shift_requirements(shift)
            )
            hours_in_shift = (shift.shift_end_dt - shift.shift_start_dt).total_hours()
            residents_acuity = self.resident_acuity_retriever.get_resident_acuity_list(
                shift
            )
            shift_census = len(residents_acuity)

            # Calculation Logic
            required_rn_hours = shift_requirements.target_hprd_rn * shift_census
            required_cna_hours = shift_requirements.target_hprd_cna * shift_census
            required_total_hours = shift_requirements.target_total_hprd * shift_census

            # Convert to Shift Hours
            hprd_shift_nurse_requirements[shift.shift_id, HprdEnforcedRole.RN] = (
                required_rn_hours / hours_in_shift
            )
            hprd_shift_nurse_requirements[shift.shift_id, HprdEnforcedRole.CNA] = (
                required_cna_hours / hours_in_shift
            )
            hprd_shift_nurse_requirements.add_total_req(
                shift, required_total_hours / hours_in_shift
            )

        return hprd_shift_nurse_requirements


class NurseHardBlockCheckerImpl(INurseHardBlockChecker):
    def check(self, nurse: "NurseProfile", shift: "Shift") -> bool:
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
                            pendulum.WeekDay.SATURDAY,
                            pendulum.WeekDay.SUNDAY,
                        }:
                            return True
        return False

        # Check 2: Max weekly/monthly hour limits (Fatigue/Compliance)
        # This is complex in LP, usually handled via SUM constraints, but included here for logic completeness

        # Check 3: Role/Skill match (RN cannot cover CNA shift if hard rule)
        # if self.config.unit_needs_rn(day_shift) and nurse.role != 'RN':
        #    return False


class ComprehensiveShiftCostStrategy(IPayModelStrategy):
    def __init__(
        self,
        burden_calc: ILaborBurdenCalculator,
        incentive_mgr: IIncentiveManager,
        # nurse_retriever: INurseRetriever,
    ):
        self.burden_calc = burden_calc
        self.incentive_mgr = incentive_mgr
        # self.nurse_retriever = nurse_retriever

    def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> List[Any]:
        terms = []

        for shift in data_provider.get_shifts():
            duration = (shift.shift_end_dt - shift.shift_start_dt).total_hours()
            nurses = data_provider.get_nurses_for_shift(shift)

            for nurse in nurses:
                var = lp_holder.get_variable(nurse.employee_id, shift.shift_id)

                employee = data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                # --- 1. Base Calculations ---
                comp_record = (
                    data_provider.get_compensation_service().get_record_for_date(
                        nurse.employee_id, shift.shift_start_dt
                    )
                )
                if not comp_record:
                    continue  # No compensation record found

                base_rate = comp_record.base_rate_effective
                if base_rate is None:
                    continue

                base_wage = base_rate * duration

                # --- 2. Shift Differentials (Shift Dependent) ---
                diff_rate = 0.0
                if not shift.day_shift:
                    diff_rate += 2.00
                if is_weekend(shift.shift_start_dt.day_of_week):
                    diff_rate += 1.50
                shift_diff_cost = diff_rate * duration

                employee = data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                # --- 3. Burden (Taxes & Benefits) ---
                # We burden the Base + Diff (usually taxes apply to diffs too)

                statutory, benefits = self.burden_calc.calculate_burden(
                    employee, base_wage + shift_diff_cost
                )

                # --- 4. Incentives (Holidays, Pickups) ---
                incentives = self.incentive_mgr.calculate_incentives(
                    shift, employee, base_rate
                )

                # --- 5. Total Decision Cost ---
                total_cost = (
                    base_wage + shift_diff_cost + statutory + benefits + incentives
                )

                terms.append(var * total_cost)

        return terms

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        pass

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        pass


class WeeklyVolumePayStrategy(IPayModelStrategy):
    """
    Implements classic weekly overtime logic using Reg/OT buckets.
    """

    def __init__(
        self,
        threshold: float = 40.0,
    ):
        self.threshold = threshold

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        # Create Reg/OT buckets for everyone
        for emp in data_provider.get_all_employees():
            lp_holder.add_pay_variables(emp.employee_id)

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        unique_employees = set(lp_holder.pay_variables.keys())

        for emp_id in unique_employees:
            pay_vars = lp_holder.get_pay_variables(emp_id)
            if not pay_vars:
                continue
            worked_hours = data_provider.get_accumulated_hours_for_pay_period(emp_id)
            remaining_cap = max(0.0, self.threshold - worked_hours)

            # Sum assigned hours
            assigned_hours = []
            for shift in data_provider.get_shifts():
                try:
                    var = lp_holder.get_variable(emp_id, shift.shift_id)
                    duration = (shift.shift_end_dt - shift.shift_start_dt).total_hours()
                    assigned_hours.append(var * duration)
                except KeyError:
                    pass

            if assigned_hours:
                # 1. Total = Reg + OT
                problem += (
                    pulp.lpSum(assigned_hours) == pay_vars["reg"] + pay_vars["ot"]
                )
                # 2. Reg Cap
                problem += pay_vars["reg"] <= remaining_cap

    def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> List[pulp.LpAffineExpression]:
        terms = []
        unique_employees = set(lp_holder.pay_variables.keys())

        # We need a reference date to look up the rate.
        # Using the start of the first shift in the window is standard practice.
        reference_date = data_provider.get_shifts()[0].shift_start_dt

        for emp_id in unique_employees:
            pay_vars = lp_holder.get_pay_variables(emp_id)

            if not pay_vars:
                continue

            comp_record = data_provider.get_compensation_service().get_record_for_date(
                emp_id, reference_date
            )
            if not comp_record:
                continue

            # Handle case where no record exists (e.g. inactive employee)
            # Assuming the property on StaffCompensationRecord is 'base_hourly_rate'

            base_rate = comp_record.base_rate_effective

            # Buckets carry the cost
            terms.append(pay_vars["reg"] * base_rate)
            terms.append(pay_vars["ot"] * (base_rate * 1.5))

        return terms


class DailyOvertimePayStrategy(IPayModelStrategy):
    def __init__(
        self,
        # staff_comp_service: IStaffCompensationService,
        # nurse_retriever: INurseRetriever,
    ) -> None:
        # self.comp_service = staff_comp_service
        # self.nurse_retriever = nurse_retriever
        pass

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        # No buckets needed for daily OT! Costs are on the shifts themselves.
        pass

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        # No complex linking constraints needed for daily OT
        pass

    def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> List[pulp.LpAffineExpression]:
        terms = []
        for shift in data_provider.get_shifts():
            duration = (shift.shift_end_dt - shift.shift_start_dt).total_hours()
            # Calculate cost ONCE here (deterministic)
            is_ot_shift = duration > 8.0

            nurses = data_provider.get_nurses_for_shift(shift)
            for nurse in nurses:
                comp_record = (
                    data_provider.get_compensation_service().get_record_for_date(
                        nurse.employee_id, shift.shift_start_dt
                    )
                )
                if not comp_record:
                    continue

                base_rate = comp_record.base_rate_effective
                if base_rate is None:
                    continue

                var = lp_holder.get_variable(nurse.employee_id, shift.shift_id)

                if is_ot_shift:
                    reg_hours = 8.0
                    ot_hours = duration - 8.0
                    cost = (reg_hours * base_rate) + (ot_hours * base_rate * 1.5)
                else:
                    cost = duration * base_rate

                terms.append(var * cost)
        return terms


class StandardLaborBurdenCalculator(ILaborBurdenCalculator):
    def __init__(self) -> None:
        # Configuration could actually come from a DB
        self.fica_rate = 0.0765  # 6.2% SS + 1.45% Medicare
        self.futa_sui_rate = 0.03  # Estimate for Unemployment
        self.work_comp_rate = 0.02  # Estimate for Nursing

        # Benefits: Usually calculated as a fixed $ per hour or % of wage
        self.benefits_load_factor = 0.15  # 15% for Health/401k/PTO

    def calculate_burden(
        self, employee: Employee, base_cost: float
    ) -> Tuple[float, float]:
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
        holidays: Set[pendulum.Date],
        urgency_threshold_days: int,
        pickup_bonus: float,
    ):
        self.holidays = holidays
        self.urgency_threshold_days = urgency_threshold_days  # e.g., 2 days
        self.pickup_bonus_amount = pickup_bonus  # e.g., $50 flat

    def calculate_incentives(
        self, shift: Shift, employee: Employee, base_rate: float
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
        days_until_shift = (shift.shift_start_dt.date() - pendulum.Date.today()).days
        if 0 <= days_until_shift <= self.urgency_threshold_days:
            total_incentive += self.pickup_bonus_amount

        # 3. Amortized Bonuses (Sunk Cost?)
        # Optimization Theory Note: Strictly speaking, a sign-on bonus is a "Sunk Cost"
        # and shouldn't affect the decision to schedule a shift today.
        # However, if you want "Total Budget Accuracy", you include it.
        # total_incentive += employee.daily_amortized_bonus

        return total_incentive


class QualityOfLifeStrategy(IObjectivePenaltyStrategy):
    def __init__(
        self,
        preference_processor: IPreferencePenaltyProcessor,  # Your existing refactored service
        nurse_retriever: INurseRetriever,
        employee_retriever: IEmployeeRetriever,
        # ml_model_retriever: IMLModelOutputsRetriever,
    ):
        self.preference_processor = preference_processor
        # self.nurse_retriever = nurse_retriever
        # self.employee_retriever = employee_retriever
        # self.ml_model_retriever = ml_model_retriever

    def get_penalty_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
        weights: PreferenceWeights,
    ) -> List[Any]:
        penalty_terms = []

        for shift in data_provider.get_shifts():
            # Get Context
            ml_outputs = data_provider.get_ml_model_outputs(shift)
            nurses = data_provider.get_nurses_for_shift(shift)

            for nurse in nurses:
                employee = data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                # Get the Variable
                try:
                    lp_var = lp_holder.get_variable(nurse.employee_id, shift.shift_id)
                except KeyError:
                    continue

                # 1. Calculate Preference Penalty (The "Soft" Constraints)
                # (Delegates to your service from Turn 2)
                pref_penalty = self.preference_processor.calculate_penalty_cost(
                    employee, nurse, shift, weights
                )

                # 2. Calculate Turnover Risk Penalty
                # (High risk nurses shouldn't be placed in "bad" shifts if possible)
                risk_score = ml_outputs.turnover_risk_scores.get(nurse.employee_id, 0.0)
                risk_penalty = 0.0
                if risk_score > 0.0:
                    # Simple logic: High risk * Configured Weight
                    risk_penalty = risk_score * weights.high_risk_shift_penalty

                # 3. Add to list
                total_penalty = pref_penalty + risk_penalty
                if total_penalty > 0:
                    penalty_terms.append(lp_var * total_penalty)

        return penalty_terms


class IScenarioDataProvider(abc.ABC):
    """
    Defines the contract for providing data to strategies during a single
    optimization run. Implementations must handle lazy loading and caching within the run scope.
    """

    @abc.abstractmethod
    def get_shifts(self) -> List["Shift"]:
        """Returns the list of shifts in the scenario."""
        pass

    @abc.abstractmethod
    def get_all_employees(self) -> List["Employee"]:
        """Returns all employees active for this scenario horizon."""
        pass

    @abc.abstractmethod
    def get_employee_by_id(self, employee_id: str) -> Optional["Employee"]:
        """Returns a specific employee by ID."""
        pass

    @abc.abstractmethod
    def get_nurses_for_shift(self, shift: "Shift") -> List["NurseProfile"]:
        """Returns available nurses for a specific shift, cached per shift."""
        pass

    @abc.abstractmethod
    def get_hprd_requirements(self) -> "HprdShiftNurseRequirementHolder":
        """Calculates (once) and returns HPRD requirements for all shifts."""
        pass

    @abc.abstractmethod
    def get_compensation_service(self) -> IStaffCompensationService:
        """Provides access to financial data scoped for this run."""
        pass

    @abc.abstractmethod
    def get_ml_model_outputs(self, shift: Shift) -> MlModelOutputs:
        pass

    @abc.abstractmethod
    def get_accumulated_hours_for_pay_period(self, employee_id: str) -> float:
        """
        Returns the total hours worked by the employee in the current pay week
        BEFORE the optimization window starts.
        """
        pass


class ScenarioDataProviderImpl(IScenarioDataProvider):
    """
    Concrete implementation that uses injected raw retrievers to fetch data
    on demand and caches results for the lifetime of this object instance.
    """

    def __init__(
        self,
        shifts: List["Shift"],  # The scope of this scenario
        config: "FacilityConfig",
        employee_retriever: "IEmployeeRetriever",
        nurse_retriever: "INurseRetriever",
        hprd_calculator: "IHprdRequirementCalculator",
        staff_comp_service: IStaffCompensationService,
        ml_model_retriever: IMLModelOutputsRetriever,
        work_history_service: IEmployeeWorkHistoryService,
        pay_period_start: pendulum.DateTime,
        optimization_start_time: pendulum.DateTime,
        min_mandates: "MinMandates",
    ):
        self._shifts = shifts
        self._config = config
        self._employee_retriever = employee_retriever
        self._nurse_retriever = nurse_retriever
        self._hprd_calculator = hprd_calculator
        self._staff_comp_service = staff_comp_service
        self._ml_model_retriever = ml_model_retriever
        self._work_history_service = work_history_service

        self.pay_period_start = pay_period_start
        self.opt_start = optimization_start_time
        self._min_mandates = min_mandates

        # Internal Caches for parameterized data
        self._shift_nurses_cache: Dict[str, List["NurseProfile"]] = {}
        self._cached_all_employees: Optional[List["Employee"]] = None
        self._cached_hprd_reqs: Optional["HprdShiftNurseRequirementHolder"] = None
        self._accumulated_hours_cache: Dict[str, float] = {}

    def get_shifts(self) -> List["Shift"]:
        return self._shifts

    # FIX 13: Removed @cached_property, used manual caching to match interface signature
    def get_all_employees(self) -> List["Employee"]:
        if self._cached_all_employees is None:
            print("Fetching all employees from source...")
            self._cached_all_employees = self._employee_retriever.get_all_employees()
        return self._cached_all_employees

    def get_employee_by_id(self, employee_id: str) -> Optional["Employee"]:
        # Simple lookup from pre-fetched list
        for emp in self.get_all_employees():
            if emp.employee_id == employee_id:
                return emp
        return None

    # FIX 14: Removed @cached_property, used manual caching
    def get_hprd_requirements(self) -> "HprdShiftNurseRequirementHolder":
        if self._cached_hprd_reqs is None:
            print("Calculating heavy HPRD math...")
            self._cached_hprd_reqs = self._hprd_calculator.calculate_requirements(
                self._shifts, self._config, self._min_mandates
            )
        return self._cached_hprd_reqs

    # --- Case 2: Parameterized data cached manually with dicts ---
    def get_nurses_for_shift(self, shift: "Shift") -> List["NurseProfile"]:
        # Use shift_id as the cache key
        if shift.shift_id not in self._shift_nurses_cache:
            print(f"Fetching nurses for shift {shift.shift_id}...")
            # Call the raw retriever
            nurses = self._nurse_retriever.get_nurses(shift)
            self._shift_nurses_cache[shift.shift_id] = nurses

        return self._shift_nurses_cache[shift.shift_id]

    def get_compensation_service(self) -> IStaffCompensationService:
        return self._staff_comp_service

    def get_ml_model_outputs(self, shift: Shift) -> MlModelOutputs:
        return self._ml_model_retriever.get_model_outputs(shift)

    def get_accumulated_hours_for_pay_period(self, employee_id: str) -> float:
        if employee_id in self._accumulated_hours_cache:
            return self._accumulated_hours_cache[employee_id]

        # 1. Fetch the raw history segments from your existing service
        history = self._work_history_service.get_processed_history_for_period(
            employee_id=employee_id, up_to_check_date=self.opt_start
        )

        # 2. Calculate the total hours (You can use the service's calculator or sum it manually here)
        # Assuming get_accumulated_hours needs specific contexts,
        # or we can do a simple sum if your segments have a 'duration' property:
        total_hours = 0.0
        for segments in history.values():
            for segment in segments:
                # Ensure the segment is within the current pay week window
                if segment.start_time >= self.pay_period_start:
                    total_hours += segment.duration_hours

        self._accumulated_hours_cache[employee_id] = total_hours
        return total_hours


class ScenarioDataProviderFactory:
    """
    Holds the raw, long-lived retriever instances and knows how to
    create a scoped ScenarioDataProviderImpl for a specific run.
    """

    def __init__(
        self,
        employee_retriever: IEmployeeRetriever,
        nurse_retriever: INurseRetriever,
        hprd_calculator: IHprdRequirementCalculator,
        staff_compensation_service: IStaffCompensationService,
        ml_model_retriever: IMLModelOutputsRetriever,
        work_history_service: IEmployeeWorkHistoryService,
    ):
        self.employee_retriever = employee_retriever
        self.nurse_retriever = nurse_retriever
        self.hprd_calculator = hprd_calculator
        self.staff_compensation_service = staff_compensation_service
        self.ml_model_retriever = ml_model_retriever
        self.work_history_service = work_history_service

    def create(
        self,
        shifts: List[Shift],
        config: FacilityConfig,
        pay_period_start: pendulum.DateTime,
        optimization_start_time: pendulum.DateTime,
        min_mandates: MinMandates,
    ) -> IScenarioDataProvider:
        return ScenarioDataProviderImpl(
            shifts=shifts,
            config=config,
            employee_retriever=self.employee_retriever,
            nurse_retriever=self.nurse_retriever,
            hprd_calculator=self.hprd_calculator,
            staff_comp_service=self.staff_compensation_service,
            ml_model_retriever=self.ml_model_retriever,
            work_history_service=self.work_history_service,
            pay_period_start=pay_period_start,
            optimization_start_time=optimization_start_time,
            min_mandates=min_mandates,
        )


class CoreVariableGenerationStrategy:
    """Defines the fundamental decision variables (Nurse X assigned to Shift Y)."""

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        shifts = data_provider.get_shifts()
        for shift in shifts:
            # Use the provider!
            nurses = data_provider.get_nurses_for_shift(shift)
            for nurse in nurses:
                lp_holder.add_variable(nurse.employee_id, shift.shift_id)


class NurseShiftScheduleOptimizer:
    """
    Formulates and solves the Acuity-Driven Nurse Scheduling ILP.

    - Using retrievers to handle simulation and real time data in same engine.
    """

    def __init__(
        self,
        provider_factory: ScenarioDataProviderFactory,
        core_variable_strategy: CoreVariableGenerationStrategy,
        pay_strategies: List[IPayModelStrategy],
        rule_strategies: List[IRuleConstraintStrategy],
        penalty_strategies: List[IObjectivePenaltyStrategy],
    ) -> None:
        self.provider_factory = provider_factory
        self.core_variable_strategy = core_variable_strategy

        self.pay_strategies = pay_strategies
        self.rule_strategies = rule_strategies
        self.penalty_strategies = penalty_strategies

    def solve(
        self,
        shifts: List[Shift],
        preference_weights: PreferenceWeights,
        facility_config: FacilityConfig,
        min_mandates: MinMandates,
        pay_period_start: pendulum.DateTime,
        optimization_start_time: Optional[pendulum.DateTime] = None,
    ) -> ScheduleOptimizationResults:
        # 1. Infer Optimization Start if not provided
        # If the caller doesn't say when the optimization starts, assume it starts
        # at the moment of the earliest shift in the list.
        if optimization_start_time is None:
            if not shifts:
                return ScheduleOptimizationResults(
                    False,
                    None,
                    None,
                    InfeasibilityReasonResult(
                        InfeasibilityReason.OTHER, "No shifts provided"
                    ),
                )
            optimization_start_time = min(s.shift_start_dt for s in shifts)

        data_provider = self.provider_factory.create(
            shifts=shifts,
            config=facility_config,
            pay_period_start=pay_period_start,
            optimization_start_time=optimization_start_time,
            min_mandates=min_mandates,
        )

        problem = LpProblem("Scheduling", LpMinimize)
        lp_vars = LpNurseShiftVariableHolder()

        # 1. Setup Variables
        self.core_variable_strategy.create_variables(lp_vars, data_provider)
        for pay_strategy in self.pay_strategies:
            pay_strategy.create_variables(lp_vars, data_provider)

        # 2. Apply Constraints
        for rule_strategy in self.rule_strategies:
            rule_strategy.apply_constraints(
                problem, lp_vars, data_provider
            )  # HPRD, Fatigue
        for pay_strategy in self.pay_strategies:
            pay_strategy.apply_constraints(problem, lp_vars, data_provider)  # OT Math

        # 3. Build Objective
        obj_terms = []
        for pay_strategy in self.pay_strategies:
            obj_terms.extend(pay_strategy.get_objective_terms(lp_vars, data_provider))
        for penalty_strategy in self.penalty_strategies:
            obj_terms.extend(
                penalty_strategy.get_penalty_terms(
                    lp_vars, data_provider, preference_weights
                )
            )

        problem += pulp.lpSum(obj_terms)

        return self.solve_finalize(problem)

    def solve_finalize(
        self,
        problem: pulp.LpProblem,
    ) -> ScheduleOptimizationResults:
        # Set up a time limit for solving to ensure fast responsiveness (e.g., 60 seconds)
        solver = pulp.PULP_CBC_CMD(timeLimit=60)
        problem.solve(solver)

        if problem.status != pulp.LpStatusOptimal:
            # print(f"Solver Status: {pulp.LpStatus[problem.status]}")
            infeasibility_reason = InfeasibilityReasonResult(
                InfeasibilityReason.OTHER,
                f"Solver did not find optimal solution. Status: {pulp.LpStatus[problem.status]}",
            )
            return ScheduleOptimizationResults(False, None, None, infeasibility_reason)

        # in the future, output sum of penalization per different constraint groups
        # e.g., sum of penalties for preference violations, overtime,
        # Turnover Risk Nurses (1st need this in ML feed to optimization)
        # * output how often schedule assigned high-risk nurses to undesirable shifts
        # * how often did we violate preferences for high-risk nurses
        # how often schedule respected pairing preferences (1st need to collect this as input from nurses)

        constraint_slacks = {
            name: constraint.slack
            for name, constraint in problem.constraints.items()
            if constraint.slack is not None
        }

        schedule = self._extract_optimized_schedule_from_lp(problem)

        return ScheduleOptimizationResults(True, schedule, constraint_slacks, None)

    @staticmethod
    def _extract_optimized_schedule_from_lp(
        lp_problem: LpProblem,
    ) -> Schedule:
        assignments: Dict[str, List[str]] = defaultdict(list)
        for v in lp_problem.variables():
            if v.varValue > 0:  # Only consider assigned shifts
                parts = v.name.split("__")
                employee_id = parts[1]
                shift_id = str(parts[2])
                # nurse = next((n for n in nurses if n.employee_id == employee_id), None)
                # shift = shifts[shift_id]
                assignments[shift_id].append(employee_id)

        return Schedule(assignments)
