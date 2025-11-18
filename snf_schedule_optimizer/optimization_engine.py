import abc
from collections import defaultdict

import numpy as np
import pendulum

from snf_schedule_optimizer.data_models.main_data_models import *
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, LpBinary
from dataclasses import dataclass

from snf_schedule_optimizer.resident_acuity_retrievers import IResidentAcuityPerShiftRetriever
from snf_schedule_optimizer.shift_requirements_retriever import IShiftRequirementsRetriever


@dataclass(frozen=True)
class PreferenceWeights:
    ot_avoidance_penalty: float = 1000.0
    team_consistency_penalty: float = 300.0
    high_risk_shift_penalty: float = 2000.0
    custom_preference_penalty: float = 1500.0


@dataclass(frozen=True)
class MlModelOutputs:
    """Stores the pre-calculated, dynamic outputs from ML models."""
    turnover_risk_scores: Dict[str, float]  # {employee_id: score}
    shift_call_out_forecast: float  # {shift_id: predicted_rate}
    unit_acuity_stress: Dict[str, float]  # {unit_id: stress_multiplier}
    team_compatibility_scores: Dict[Tuple[str, str], float]  # {(nurse_A, nurse_B): score}


N_FORECAST_AHEAD_DAYS = 14


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


class INurseCanCoverShiftFunc(abc.ABC):
    @abc.abstractmethod
    def __call__(self, nurse: NurseProfile, shift: Shift) -> bool:
        pass


class NurseCanCoverShiftPreferencesFn(INurseCanCoverShiftFunc):
    def __call__(self, nurse: NurseProfile, shift: Shift) -> bool:
        # Check 1: Mandatory time off blocks (from StaffPreference)
        if self._is_hard_block(nurse, shift):
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
        if nurse.custom_preferences:
            for pref in nurse.custom_preferences:
                if pref.is_hard_block:
                    if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                        if shift.day_of_week == pref.specific_day:
                            return True
                    elif pref.preference_type == PreferenceType.WEEKEND_OFF:
                        if shift.day_of_week in {pendulum.WeekDay.SATURDAY, pendulum.WeekDay.SUNDAY}:
                            return True
        return False


class IPreferencePenaltyCalculator(abc.ABC):
    @abc.abstractmethod
    def __call__(
            self,
            nurse: NurseProfile,
            shift: Shift,
            preference_weights: PreferenceWeights,
    ) -> float:
        pass


class PreferencePenaltyCalculatorImpl(IPreferencePenaltyCalculator):
    def __call__(
            self,
            nurse: NurseProfile,
            shift: Shift,
            preference_weights: PreferenceWeights,
    ) -> float:
        """
        Calculates the non-financial penalty cost if the assignment violates a soft preference.
        This cost is added to the LP objective function.
        """
        penalty = 0.0

        # Penalize assigning a nurse to a night shift if they prefer days
        if not shift.day_shift:
            if (
                    nurse.custom_preferences and
                    any(p for p in nurse.custom_preferences if p.preference_type.DAY_SHIFT_PREFERENCE)
            ):
                # The 'weights' parameter controls the impact of this penalty on the solver
                penalty += preference_weights.custom_preference_penalty

        if shift.day_shift:
            if (
                    nurse.custom_preferences and
                    any(p for p in nurse.custom_preferences if p.preference_type.NIGHT_SHIFT_PREFERENCE)
            ):
                penalty += preference_weights.custom_preference_penalty

        if nurse.custom_preferences is not None:
            if any(
                    p.preference_type == PreferenceType.SPECIFIC_DAY_OFF and
                    p.specific_day == shift.day_of_week
                    for p in nurse.custom_preferences
            ):
                penalty += preference_weights.custom_preference_penalty

        # Penalize overtime assignment (if not agency, and deemed undesirable)
        if self._is_overtime_risk(nurse, shift.day_shift):
            penalty += preference_weights.ot_avoidance_penalty * nurse.ot_multiplier

        # Future implementation: Incorporate penalties for breaking team consistency here
        # 

        return penalty

    @staticmethod
    def _is_overtime_risk(nurse: NurseProfile, day_shift: int) -> bool:
        """
        Predictive check: Determines if assigning this shift will push the nurse into OT.
        This logic is complex and requires knowledge of past scheduled shifts.
        """
        # Placeholder: In a real system, this would query scheduled hours from the DB.
        # For this structure, we assume an abstract complexity check.
        # if nurse.scheduled_hours_to_date > 32 and nurse.role != 'Agency':
        #     return True
        return False


class IShiftCostCalculator(abc.ABC):
    @abc.abstractmethod
    def __call__(self, nurse: NurseProfile, shift: Shift) -> float:
        pass


class ShiftCostCalculatorImpl(IShiftCostCalculator):
    def __init__(self, facility_config: FacilityConfig):
        self.facility_config = facility_config

    def __call__(self, nurse: NurseProfile, shift: Shift) -> float:
        """
        Calculates the true financial cost (Base + Premium) of assigning this nurse
        to this specific shift.
        """
        # Simplification: Assume all shifts are 8 hours.
        base_cost = nurse.hourly_cost_base * shift.duration_hours

        # Logic for mandatory overtime (e.g., beyond 40 hours/week or certain shifts)
        # For simplicity, we mock a premium for weekend shifts (shift 6, 7, 13, 14 are examples)
        if NurseShiftScheduleOptimizer.is_weekend(shift.day_of_week):
            return base_cost * self.facility_config.weekend_multiplier

        if not shift.day_shift:
            return base_cost * self.facility_config.night_shift_multiplier

        return base_cost


@dataclass(frozen=True)
class ScheduleOptimizationParams:
    pass


@dataclass(frozen=True)
class ScheduleOptimizationResults:
    success: bool
    optimal_schedule: Optional[Schedule]
    constraint_slacks: Optional[Dict[str, float]]


class HprdShiftNurseRequirements:
    """
    Stores the required HPRD-adjusted nurse hours per shift and role.
    """

    def __init__(
            self,
            shifts: List[str],  # shift_ids
            roles: List[NurseRole],
    ):
        # self.values: np.ndarray[Any, np.dtype[np.float64]]  # Shape: (n_shifts, n_roles)
        self.values = np.zeros((len(shifts), len(roles) + 1))

        self.shifts = shifts  # shift_ids
        self.roles = roles

    def __setitem__(self, key: Tuple[str, NurseRole], value: float) -> None:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        self.values[shift_idx, role_idx] = value

    def __getitem__(self, key: Tuple[str, NurseRole]) -> float:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        return float(self.values[shift_idx, role_idx])

    def add_total_req(self, shift: Shift, value: float) -> None:
        shift_idx = self.shifts.index(shift.shift_id)
        self.values[shift_idx, -1] += value

    def get_total_req(self, shift_str: str) -> float:
        shift_idx = self.shifts.index(shift_str)
        return float(self.values[shift_idx, -1])


class INurseRetriever(abc.ABC):
    @abc.abstractmethod
    def get_nurses(
            self,
            shift: Shift,
    ) -> List[NurseProfile]:
        pass


class NurseRetrieverImpl(INurseRetriever):
    def __init__(
            self,
            nurses: List[NurseProfile],
    ):
        self.nurses = nurses

    def get_nurses(
            self,
            shift: Shift,
    ) -> List[NurseProfile]:
        # In a real implementation, filter nurses based on availability, skills, etc.
        return self.nurses

class IMLModelOutputsRetriever(abc.ABC):
    @abc.abstractmethod
    def get_model_outputs(
            self,
            shift: Shift,
    ) -> MlModelOutputs:
        pass


class MLModelOutputsRetrieverImpl(IMLModelOutputsRetriever):
    def get_model_outputs(
            self,
            shift: Shift,
    ) -> MlModelOutputs:
        return MlModelOutputs(
            turnover_risk_scores={},
            shift_call_out_forecast=0.0,
            unit_acuity_stress={},
            team_compatibility_scores={}
        )


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
    ) -> None:
        self.check_nurse_can_cover_shift_func = NurseCanCoverShiftPreferencesFn()
        self.resident_acuity_retriever = resident_acuity_retriever
        self.shift_requirements_retriever = shift_requirements_retriever
        self.nurse_retriever = nurse_retriever
        self.ml_model_outputs_retriever = ml_model_outputs_retriever

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
        self.populate_nurse_shift_lp_variables(shifts, lp_vars_holder)
        required_hprd_role_req_hours = self._calculate_hprd_shift_role_req_hours(
            shifts,
            facility_config,
            min_mandate
        )

        self.add_constraints(
            required_hprd_role_req_hours,
            shifts,
            facility_hr_config,
            problem,
            lp_vars_holder,
        )

        shift_cost_calculator = ShiftCostCalculatorImpl(facility_config)

        problem = self.set_objective_function(
            shifts,
            lp_vars_holder,
            preference_weights,
            problem,
            shift_cost_calculator,
            PreferencePenaltyCalculatorImpl()
        )

        # Set up a time limit for solving to ensure fast responsiveness (e.g., 60 seconds)
        solver = pulp.PULP_CBC_CMD(timeLimit=60)
        problem.solve(solver)

        if problem.status != pulp.LpStatusOptimal:
            print(f"Solver Status: {pulp.LpStatus[problem.status]}")

            return ScheduleOptimizationResults(
                False,
                None,
                None
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

        schedule = NurseShiftScheduleOptimizer._extract_optimized_schedule_from_lp(problem)

        return ScheduleOptimizationResults(
            True,
            schedule,
            constraint_slacks
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

    def add_constraints(
            self,
            required_nurse_hprd_count: HprdShiftNurseRequirements,
            shifts: List[Shift],
            facility_hr_config: FacilityHrConfig,
            problem: LpProblem,
            lp_variables_holder: LpNurseShiftVariableHolder,
    ) -> None:
        """Mandatory constraints from FacilityConfig and staffing laws."""

        # 1. HPRD Coverage (The Core Constraint)
        for shift in shifts:
            for nurse_role in required_nurse_hprd_count.roles:
                required_count = required_nurse_hprd_count[shift.shift_id, nurse_role]
                if required_count > 0:
                    all_nurses = self.nurse_retriever.get_nurses(shift)
                    total_staffed_nurses = sum(
                        lp_variables_holder.get_variable(n.employee_id, shift.shift_id)
                        for n in all_nurses
                        if n.role == nurse_role and self.check_nurse_can_cover_shift_func(n, shift)
                    )
                    problem += total_staffed_nurses >= required_count, \
                        f"HPRD_Min_Nurse_Count__{shift.shift_id}__{nurse_role.value}"

        # 2. Fatigue/Rest hard constraint
        # Ensure no nurse works consecutive shifts without adequate rest.
        # not customizable now since nurses shouldn't be able to work back-to-back shifts
        for i, shift in enumerate(shifts[:-1]):
            all_nurses = self.nurse_retriever.get_nurses(shift)
            for nurse in all_nurses:
                current_shift = shifts[i]
                next_shift = shifts[i + 1]
                problem += (
                    lp_variables_holder.get_variable(nurse.employee_id, current_shift.shift_id)
                    + lp_variables_holder.get_variable(nurse.employee_id, next_shift.shift_id) <= 1,
                    f"Fatigue__{nurse.employee_id}__{current_shift.shift_id}"
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

    def set_objective_function(
            self,
            shifts: List[Shift],
            var_holder: LpNurseShiftVariableHolder,
            preference_weights: PreferenceWeights,
            problem: LpProblem,
            shift_cost_calculator: IShiftCostCalculator,
            calculate_preference_penalty: IPreferencePenaltyCalculator,
    ) -> LpProblem:
        """Sets the objective: Minimize cost while penalizing soft constraint violations.
        """
        total_cost_expression = []

        for shift in shifts:
            get_model_outputs = self.ml_model_outputs_retriever.get_model_outputs(shift)
            nurses = self.nurse_retriever.get_nurses(shift)
            for nurse in nurses:
                turnover_risk = get_model_outputs.turnover_risk_scores.get(nurse.employee_id, 0.0)

                var = var_holder.get_variable(nurse.employee_id, shift.shift_id)
                cost = shift_cost_calculator(nurse, shift)  # Includes OT/Agency multipliers

                # Add preference penalties as a weighted cost
                penalty_cost = calculate_preference_penalty(nurse, shift, preference_weights)

                if turnover_risk > 0.0:
                    penalty_cost += turnover_risk * preference_weights.high_risk_shift_penalty

                total_cost_expression += (cost + penalty_cost) * var

        problem += pulp.lpSum(total_cost_expression), "Total_Weighted_Cost"

        return problem

    @staticmethod
    def build_problem() -> LpProblem:
        return LpProblem("Optimal_Schedule", LpMinimize)

    def populate_nurse_shift_lp_variables(
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
            # residents_per_shift: Dict[str, List[ResidentAcuity]],  # shift_id -> resident acuity list
            shifts: List[Shift],
            config: FacilityConfig,
            min_mandate: MinMandates,
    ) -> HprdShiftNurseRequirements:
        """
        Calculates the acuity-adjusted mandated nursing hours (HPRD) required
        for each unit and shift across all shifts in the forecast horizon.

        # Output: {('Shift_1_RN', Shift(...)): 12.5, ('Shift_2_CNA', Shift(...)): 50.0, ...}
        """

        # Placeholder for complex Acuity-to-HPRD conversion (Your core IP)
        # This function would call predictive_ml._calculate_required_minutes(resident)
        # for each resident and aggregate by unit/shift.

        hprd_shift_nurse_requirements = HprdShiftNurseRequirements(
            [s.shift_id for s in shifts],
            [NurseRole.RN, NurseRole.CNA]
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

            hprd_shift_nurse_requirements[shift.shift_id, NurseRole.RN] = required_rn_shift_hours
            hprd_shift_nurse_requirements[shift.shift_id, NurseRole.CNA] = required_cna_shift_hours
            hprd_shift_nurse_requirements.add_total_req(shift, required_total_shift_hours)

        return hprd_shift_nurse_requirements

    @staticmethod
    def is_weekend(day_of_week: pendulum.WeekDay) -> bool:
        """Helper to determine if a given day is a weekend."""
        return day_of_week in {pendulum.WeekDay.SATURDAY, pendulum.WeekDay.SUNDAY}

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
        if nurse.custom_preferences:
            for pref in nurse.custom_preferences:
                if pref.is_hard_block:
                    if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                        if shift.day_of_week == pref.specific_day:
                            return True
                    elif pref.preference_type == PreferenceType.WEEKEND_OFF:
                        if NurseShiftScheduleOptimizer.is_weekend(shift.day_of_week):
                            return True
        return False
