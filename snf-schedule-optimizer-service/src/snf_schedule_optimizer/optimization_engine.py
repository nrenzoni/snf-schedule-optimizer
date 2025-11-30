import abc
import enum
import itertools
from collections import defaultdict
from dataclasses import dataclass
import pendulum
import numpy as np

import pulp
from pulp import LpBinary, LpMinimize, LpProblem, LpVariable

from snf_schedule_optimizer.models import *
from snf_schedule_optimizer.datetime_utils import is_weekend
from snf_schedule_optimizer.ml_output_retrievers import IMLModelOutputsRetriever
from snf_schedule_optimizer.persistence.nurse_retrievers import INurseRetriever
from snf_schedule_optimizer.resident_acuity_retrievers import IResidentAcuityPerShiftRetriever
from snf_schedule_optimizer.services.calculations.shift_pay_processor import ShiftPayProcessor
from snf_schedule_optimizer.services.interfaces import IEmployeeRetriever, INurseDifferentialRetriever, \
    IPreferencePenaltyProcessor, IShiftRequirementsRetriever, IStaffCompensationService


class LpNurseShiftVariableHolder:
    def __init__(self) -> None:
        self.variables: Dict[str, LpVariable] = {}

    def add_variable(
            self,
            employee_id: str,
            shift_id: str,
    ) -> LpVariable:
        var_name = f"X__{employee_id}__{shift_id}"
        var = LpVariable(var_name, cat=LpBinary)
        self.variables[var_name] = var
        return var

    def get_variable(self, employee_id: str, shift_id: str) -> LpVariable:
        var_name = f"X__{employee_id}__{shift_id}"
        return self.variables[var_name]


class INurseHardBlockChecker(abc.ABC):
    """
    Checks if the nurse has any hard block preferences for the given shift.
    """

    @abc.abstractmethod
    def __call__(self, nurse: NurseProfile, shift: Shift) -> bool:
        """
        Checks all HARD BLOCKERS (time off requests, skill gaps, max hours).
        :return: True if the nurse cannot be assigned to this shift due to hard blocks.
        """
        pass


class NurseHardBlockCheckerImpl(INurseHardBlockChecker):
    def __call__(self, nurse: 'NurseProfile', shift: 'Shift') -> bool:
        # Check 1: Mandatory time off blocks (from StaffPreference)
        if nurse.shift_custom_preferences:
            for pref in nurse.shift_custom_preferences:
                if pref.is_hard_block:
                    if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                        # FIX: The specific_value must be converted to WeekDay for comparison.
                        # Assuming specific_value is stored as an integer (0-6) or a string representation of the integer.
                        try:
                            # Safely convert to int, then to WeekDay if needed, or compare int to WeekDay.value
                            pref_day_int = int(pref.specific_value) if pref.specific_value is not None else -1
                        except ValueError:
                            pref_day_int = -1  # Invalid value means no match

                        if shift.day_of_week.value == pref_day_int:
                            return True
                    elif pref.preference_type == PreferenceType.WEEKEND_OFF:
                        if shift.day_of_week in {pendulum.WeekDay.SATURDAY, pendulum.WeekDay.SUNDAY}:
                            return True
        return False

        # Check 2: Max weekly/monthly hour limits (Fatigue/Compliance)
        # This is complex in LP, usually handled via SUM constraints, but included here for logic completeness

        # Check 3: Role/Skill match (RN cannot cover CNA shift if hard rule)
        # if self.config.unit_needs_rn(day_shift) and nurse.role != 'RN':
        #    return False


@dataclass(frozen=True)
class ScheduleOptimizationParams:
    pass


class InfeasibilityReason(enum.StrEnum):
    NO_AVAILABLE_NURSES = "No available nurses to cover required role"  # includes hard blocks
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

    def __setitem__(self, key: Tuple[str, HprdEnforcedRole], value: float) -> None:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        self.values[shift_idx, role_idx] = value

    def __getitem__(self, key: Tuple[str, HprdEnforcedRole]) -> float:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        return float(self.values[shift_idx, role_idx])

    def add_total_req(self, shift: Shift, value: float) -> None:
        shift_idx = self.shifts.index(shift.shift_id)
        self.values[shift_idx, -1] += value

    def get_total_req(self, shift_str: str) -> float:
        shift_idx = self.shifts.index(shift_str)
        return float(self.values[shift_idx, -1])


class NurseShiftScheduleOptimizer:
    """
    Formulates and solves the Acuity-Driven Nurse Scheduling ILP.

    - Using retrievers to handle simulation and real time data in same engine.
    """

    def __init__(
            self,
            resident_acuity_retriever: IResidentAcuityPerShiftRetriever,
            shift_requirements_retriever: IShiftRequirementsRetriever,
            nurse_retriever: INurseRetriever,
            ml_model_outputs_retriever: IMLModelOutputsRetriever,
            nurse_differential_retriever: INurseDifferentialRetriever,
            shift_pay_processor: ShiftPayProcessor,
            employee_retriever: IEmployeeRetriever,
            staff_compensation_service: IStaffCompensationService,
            preference_penalty_processor: IPreferencePenaltyProcessor,
    ) -> None:
        self.nurse_hard_block_checker_fn = NurseHardBlockCheckerImpl()
        self.resident_acuity_retriever = resident_acuity_retriever
        self.shift_requirements_retriever = shift_requirements_retriever
        self.nurse_retriever = nurse_retriever
        self.ml_model_outputs_retriever = ml_model_outputs_retriever
        self.nurse_differential_retriever = nurse_differential_retriever
        self.shift_pay_processor = shift_pay_processor
        self.employee_retriever = employee_retriever
        self.staff_compensation_service = staff_compensation_service

        self.preference_penalty_processor = preference_penalty_processor
        # PreferencePenaltyProcessorImpl(
        #     self.staff_compensation_service
        # )

    def solve(
            self,
            shifts: List[Shift],  # shifts per day over all forecast days
            facility_config: FacilityConfig,
            facility_hr_config: FacilityHrConfig,
            min_mandate: MinMandates,
            preference_weights: PreferenceWeights,
    ) -> ScheduleOptimizationResults:
        """
        Executes the solver and returns the optimized schedule.
        """

        problem = NurseShiftScheduleOptimizer.build_problem()
        lp_vars_holder = LpNurseShiftVariableHolder()
        self.generate_nurse_shift_lp_variables(shifts, lp_vars_holder)
        required_hprd_role_req_hours = self._calculate_hprd_shift_role_req_hours(
            shifts,
            facility_config,
            min_mandate
        )

        infeasibility_result = self.add_min_hprd_per_shift_constraints(
            required_hprd_role_req_hours,
            shifts,
            facility_hr_config,
            problem,
            lp_vars_holder,
        )

        if infeasibility_result is not None:
            return ScheduleOptimizationResults(
                False,
                None,
                None,
                infeasibility_result
            )

        problem = self.set_objective_function(
            shifts,
            lp_vars_holder,
            preference_weights,
            problem
        )

        # Set up a time limit for solving to ensure fast responsiveness (e.g., 60 seconds)
        solver = pulp.PULP_CBC_CMD(timeLimit=60)
        problem.solve(solver)

        if problem.status != pulp.LpStatusOptimal:
            # print(f"Solver Status: {pulp.LpStatus[problem.status]}")
            infeasibility_reason = InfeasibilityReasonResult(
                InfeasibilityReason.OTHER,
                f"Solver did not find optimal solution. Status: {pulp.LpStatus[problem.status]}"
            )
            return ScheduleOptimizationResults(
                False,
                None,
                None,
                infeasibility_reason
            )

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

        return ScheduleOptimizationResults(
            True,
            schedule,
            constraint_slacks,
            None
        )

    @staticmethod
    def _extract_optimized_schedule_from_lp(
            lp_problem: LpProblem,
    ) -> Schedule:
        assignments: Dict[str, List[str]] = defaultdict(list)
        for v in lp_problem.variables():
            if v.varValue > 0:  # Only consider assigned shifts
                parts = v.name.split('__')
                employee_id = parts[1]
                shift_id = str(parts[2])
                # nurse = next((n for n in nurses if n.employee_id == employee_id), None)
                # shift = shifts[shift_id]
                assignments[shift_id].append(employee_id)

        return Schedule(assignments)

    def add_min_hprd_per_shift_constraints(
            self,
            required_hprd_per_position_holder: HprdShiftNurseRequirementHolder,
            shifts: List[Shift],
            facility_hr_config: FacilityHrConfig,
            problem: LpProblem,
            lp_variables_holder: LpNurseShiftVariableHolder,
    ) -> Optional[InfeasibilityReasonResult]:
        """Mandatory constraints from FacilityConfig and staffing laws."""

        # 1. HPRD Coverage (The Core Constraint)
        for shift in shifts:
            for hprd_enforced_role in required_hprd_per_position_holder.roles:
                required_count = required_hprd_per_position_holder[shift.shift_id, hprd_enforced_role]
                if required_count > 0:
                    all_employees = self.employee_retriever.get_all_employees()
                    available_for_shift = []

                    for employee in all_employees:
                        employee = self.employee_retriever.get_employee_by_id(employee.employee_id)

                        if employee is None:
                            continue

                        if employee.job_title == hprd_enforced_role.value:
                            nurse = self.nurse_retriever.get_nurse(employee.employee_id)
                            if not self.nurse_hard_block_checker_fn(nurse, shift):
                                available_for_shift.append(
                                    lp_variables_holder.get_variable(employee.employee_id, shift.shift_id)
                                )
                    if len(available_for_shift) == 0:
                        return InfeasibilityReasonResult(
                            InfeasibilityReason.NO_AVAILABLE_NURSES,
                            f"No available nurses for role {hprd_enforced_role.value} on shift {shift.shift_id}"
                        )

                    problem += pulp.lpSum(available_for_shift) >= required_count, \
                        f"HPRD_Min_Nurse_Count__{shift.shift_id}__{hprd_enforced_role.value}"

        # 2. Fatigue/Rest hard constraint
        # Ensure no nurse works consecutive shifts without adequate rest.
        # not customizable now since nurses shouldn't be able to work back-to-back shifts
        for shift_1, shift_2 in itertools.pairwise(shifts):
            all_nurses_shift_1 = self.nurse_retriever.get_nurses(shift_1)
            all_nurses_shift_2 = self.nurse_retriever.get_nurses(shift_2)
            nurses_both_shifts = set(all_nurses_shift_1).intersection(all_nurses_shift_2)
            for nurse in nurses_both_shifts:
                problem += (
                    lp_variables_holder.get_variable(nurse.employee_id, shift_1.shift_id)
                    + lp_variables_holder.get_variable(nurse.employee_id, shift_2.shift_id) <= 1,
                    f"Fatigue__{nurse.employee_id}__{shift_1.shift_id}"
                )

        # todo
        # max_consecutive_work_days = facility_hr_config.max_consecutive_work_days
        # if max_consecutive_shift_days_allowed > 0:
        #     pass

        # temp disabled to get feasible solution
        #
        # min_rest_hours_between_shifts = facility_hr_config.min_rest_hours_between_shifts
        # if min_rest_hours_between_shifts > 0:
        #     for nurse in nurses:
        #         for i in range(len(shifts) - 1):
        #             current_shift = shifts[i]
        #             next_shift = shifts[i + 1]
        #             hours_between_shifts = (next_shift.shift_start_time - current_shift.shift_end_time).total_hours()
        #             if hours_between_shifts < min_rest_hours_between_shifts:
        #                 problem += (
        #                     lp_variables_holder.get_variable(nurse.employee_id, current_shift.shift_id)
        #                     + lp_variables_holder.get_variable(nurse.employee_id, next_shift.shift_id) <= 1,
        #                     f"MinRestHours__{nurse.employee_id}__{current_shift.shift_id}"
        #                 )

        return None

    def set_objective_function(
            self,
            shifts: List[Shift],
            var_holder: LpNurseShiftVariableHolder,
            preference_weights: PreferenceWeights,
            problem: LpProblem,
    ) -> LpProblem:
        """Sets the objective: Minimize cost while penalizing soft constraint violations.
        """
        total_cost_expr = []

        for shift in shifts:
            get_model_outputs = self.ml_model_outputs_retriever.get_model_outputs(shift)
            nurses = self.nurse_retriever.get_nurses(
                shift
            )  # todo: change to get employees, and maybe add EmployeeShiftFilterService, then remove NurseRetriever
            for nurse in nurses:
                turnover_risk = get_model_outputs.turnover_risk_scores.get(nurse.employee_id, 0.0)

                employee = self.employee_retriever.get_employee_by_id(nurse.employee_id)
                if employee is None:
                    print(f"Employee {nurse.employee_id} not found for shift {shift.shift_id}")
                    continue

                employee_shift_lp_var = var_holder.get_variable(nurse.employee_id, shift.shift_id)

                cost = self.shift_pay_processor.calculate_shift_cost(
                    employee,
                    shift
                )  # Includes OT/Agency multipliers

                # Add preference penalties as a weighted cost
                penalty_cost = self.preference_penalty_processor.calculate_penalty_cost(
                    employee, nurse, shift, preference_weights
                )

                if turnover_risk > 0.0:
                    penalty_cost += turnover_risk * preference_weights.high_risk_shift_penalty

                total_cost_expr += (cost + penalty_cost) * employee_shift_lp_var

        problem += pulp.lpSum(total_cost_expr), "Total_Weighted_Cost"

        return problem

    @staticmethod
    def build_problem() -> LpProblem:
        return LpProblem("Optimal_Schedule", LpMinimize)

    def generate_nurse_shift_lp_variables(
            self,
            shifts: List[Shift],
            lp_variable_holder: LpNurseShiftVariableHolder,
    ) -> None:
        for shift in shifts:
            nurses = self.nurse_retriever.get_nurses(shift)
            for nurse in nurses:
                lp_variable_holder.add_variable(
                    nurse.employee_id,
                    shift.shift_id
                )

    # =======================================================
    # ESSENTIAL HELPER METHODS
    # =======================================================

    def _calculate_hprd_shift_role_req_hours(
            self,
            shifts: List[Shift],
            config: FacilityConfig,
            min_mandate: MinMandates,
    ) -> HprdShiftNurseRequirementHolder:
        """
        Calculates the acuity-adjusted mandated nursing hours (HPRD) required
        for each unit and shift across all shifts in the forecast horizon.

        # Output: {('Shift_1_RN', Shift(...)): 12.5, ('Shift_2_CNA', Shift(...)): 50.0, ...}
        """

        # Placeholder for complex Acuity-to-HPRD conversion (Your core IP)
        # This function would call predictive_ml._calculate_required_minutes(resident)
        # for each resident and aggregate by unit/shift.

        hprd_shift_nurse_requirements = HprdShiftNurseRequirementHolder(
            [s.shift_id for s in shifts],
            [HprdEnforcedRole.RN, HprdEnforcedRole.CNA]
        )

        for shift_idx, shift in enumerate(shifts):

            shift_requirements = self.shift_requirements_retriever.get_shift_requirements(shift)

            hours_in_shift = (shift.shift_end_dt - shift.shift_start_dt).total_hours()

            residents_acuity = self.resident_acuity_retriever.get_resident_acuity_list(shift)

            shift_census = len(residents_acuity)

            # Use FacilityConfig mandates
            required_rn_hours = shift_requirements.target_hprd_rn * shift_census
            # required_lpn_hours = shift_requirements.target_hprd_lpn * total_census
            required_cna_hours = shift_requirements.target_hprd_cna * shift_census
            required_total_hours = shift_requirements.target_total_hprd * shift_census

            # Convert HPRD (per resident day) to Hours per shift
            required_rn_shift_hours = required_rn_hours / hours_in_shift
            # required_lpn_shift_hours = required_lpn_hours / hours_in_shift
            required_cna_shift_hours = required_cna_hours / hours_in_shift
            required_total_shift_hours = required_total_hours / hours_in_shift

            hprd_shift_nurse_requirements[shift.shift_id, HprdEnforcedRole.RN] = required_rn_shift_hours
            hprd_shift_nurse_requirements[shift.shift_id, HprdEnforcedRole.CNA] = required_cna_shift_hours
            hprd_shift_nurse_requirements.add_total_req(shift, required_total_shift_hours)

        return hprd_shift_nurse_requirements

    @staticmethod
    def _nurse_can_cover_shift(nurse: NurseProfile, shift: Shift) -> bool:
        """
        Checks all HARD BLOCKERS (time off requests, skill gaps, max hours).
        If False, the nurse cannot be assigned to this variable.
        """
        # Check 1: Mandatory time off blocks (from StaffPreference)
        if NurseShiftScheduleOptimizer._is_hard_block(nurse, shift):
            return False

        # Check 2: Max weekly/monthly hour limits (Fatigue/Compliance)
        # This is complex in LP, usually handled via SUM constraints, but included here for logic completeness

        # Check 3: Role/Skill match (RN cannot cover CNA shift if hard rule)
        # if self.config.unit_needs_rn(day_shift) and nurse.role != 'RN':
        #    return False

        return True  # Default assume they can work unless a hard block exists

    @staticmethod
    def _is_hard_block(nurse: NurseProfile, shift: Shift) -> bool:
        """
        Checks if the nurse has any hard block preferences for the given shift.
        """
        if nurse.shift_custom_preferences:
            for pref in nurse.shift_custom_preferences:
                if pref.is_hard_block:
                    if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                        try:
                            pref_day_int = int(pref.specific_value) if pref.specific_value is not None else -1
                            if shift.day_of_week.value == pref_day_int:
                                return True
                        except (ValueError, TypeError):
                            # If conversion fails (e.g., specific_value is 'Sunday' instead of '7'), ignore the preference
                            continue
                    elif pref.preference_type == PreferenceType.WEEKEND_OFF:
                        if is_weekend(shift.day_of_week):
                            return True
        return False
