import abc

import numpy as np
import pendulum

from snf_schedule_optimizer.data_models.main_data_models import *
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, LpBinary
from dataclasses import dataclass


@dataclass(frozen=True)
class PreferenceWeights:
    ot_avoidance_penalty: float = 1000.0
    team_consistency_penalty: float = 300.0
    high_risk_shift_penalty: float = 2000.0
    custom_preference_penalty: float = 1500.0


@dataclass(frozen=True)
class Shift:
    shift_id: str
    shift_number: int
    day_shift: bool
    day_of_week: DayOfWeek
    shift_start_time: pendulum.DateTime
    shift_end_time: pendulum.DateTime
    timezone: pendulum.Timezone

    @property
    def duration_hours(self) -> float:
        return (self.shift_end_time - self.shift_start_time).total_hours()


@dataclass(frozen=True)
class MlModelOutputs:
    """Stores the pre-calculated, dynamic inputs from ML models."""
    turnover_risk_scores: Dict[str, float]  # {employee_id: score}
    shift_call_out_forecast: Dict[str, float]  # {shift_id: predicted_rate}
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
        var_name = f"X_{employee_id}_{shift_id}"
        var = LpVariable(var_name, cat=LpBinary)
        self.variables[var_name] = var
        return var

    def get_variable(self, employee_id: str, shift_id: str) -> LpVariable:
        var_name = f"X_{employee_id}_{shift_id}"
        return self.variables[var_name]


class INurseCanCoverShiftFunc(abc.ABC):
    @abc.abstractmethod
    def __call__(self, nurse: NurseProfile, shift: Shift) -> bool:
        pass


class NurseCanCoverShiftImpl(INurseCanCoverShiftFunc):
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
                        if shift.day_of_week in {DayOfWeek.SATURDAY, DayOfWeek.SUNDAY}:
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
    def __call__(self, nurse: NurseProfile, shift: Shift) -> float:
        """
        Calculates the true financial cost (Base + Premium) of assigning this nurse
        to this specific shift.
        """
        # Simplification: Assume all shifts are 8 hours.
        base_cost = nurse.hourly_cost_base * shift.duration_hours

        # Logic for mandatory overtime (e.g., beyond 40 hours/week or certain shifts)
        # For simplicity, we mock a premium for weekend shifts (shift 6, 7, 13, 14 are examples)
        if ScheduleOptimizer.is_weekend(shift.day_of_week):
            return base_cost * 1.25  # Mock 25% shift differential for weekends

        if not shift.day_shift:
            return base_cost * 1.15  # Mock 15% shift differential for night shifts

        return base_cost


@dataclass(frozen=True)
class ScheduleOptimizationParams:
    pass


@dataclass(frozen=True)
class ScheduleOptimizationResults:
    success: bool
    optimal_schedule: Optional[Schedule]  # {variable_name: value}


@dataclass(frozen=True)
class HprdShiftNurseRequirements:
    values: np.ndarray[Any, np.dtype[np.float64]]  # Shape: (n_shifts, n_roles)
    shifts: List[Shift]
    roles: List[NurseRole]

    def __getitem__(self, key: Tuple[Shift, NurseRole]) -> float:
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        return float(self.values[shift_idx, role_idx])


# 14 day optimization, i.e., 2 weeks ahead
class ScheduleOptimizer:
    """Formulates and solves the Acuity-Driven Nurse Scheduling ILP."""

    @staticmethod
    def solve(
            nurses: List[NurseProfile],
            residents: List[ResidentAcuity],
            shifts: List[Shift],  # shifts per day over all forecast days
            facility_params: FacilityConfig,
            min_mandate: MinMandates,
            preference_weights: PreferenceWeights,
            shift_requirements: ShiftSpecificRequirements,
            model_outputs: MlModelOutputs,
    ) -> ScheduleOptimizationResults:
        """
        Executes the solver and returns the optimized schedule.
        """
        problem = ScheduleOptimizer.build_problem()
        lp_vars_holder = LpNurseShiftVariableHolder()
        ScheduleOptimizer.add_lp_variable_per_nurse_shift(nurses, shifts, lp_vars_holder)
        required_hprd_role_req_hours = ScheduleOptimizer._calculate_hprd_shift_role_req_hours(
            residents,
            shifts,
            facility_params,
            shift_requirements,
            min_mandate
        )
        ScheduleOptimizer.add_hard_constraints(
            required_hprd_role_req_hours,
            shifts,
            NURSE_ROLES,
            nurses,
            problem,
            lp_vars_holder,
            NurseCanCoverShiftImpl()
        )

        problem = ScheduleOptimizer.set_objective_function(
            shifts,
            nurses,
            lp_vars_holder,
            preference_weights,
            problem,
            ShiftCostCalculatorImpl(),
            model_outputs,
            PreferencePenaltyCalculatorImpl()
        )

        # Set up a time limit for solving to ensure fast responsiveness (e.g., 60 seconds)
        solver = pulp.PULP_CBC_CMD(timeLimit=60)
        problem.solve(solver)

        if pulp.LpStatus[problem.status] != "Optimal":
            print(f"Solver Status: {pulp.LpStatus[problem.status]}")
            return ScheduleOptimizationResults(
                False,
                None
            )

        # in the future, output sum of penalization per different constraint groups
        # e.g., sum of penalties for preference violations, overtime,
        # Turnover Risk Nurses (1st need this in ML feed to optimization)
        # * output how often schedule assigned high-risk nurses to undesirable shifts
        # * how often did we violate preferences for high-risk nurses
        # how often schedule respected pairing preferences (1st need to collect this as input from nurses)

        return ScheduleOptimizationResults(
            True,
            ScheduleOptimizer._extract_optimized_schedule_from_lp(problem)
        )

    @staticmethod
    def _extract_optimized_schedule_from_lp(lp_problem: LpProblem) -> Schedule:
        assignments: Dict[str, List[int]] = {}
        for v in lp_problem.variables():
            if v.varValue > 0:  # Only consider assigned shifts
                parts = v.name.split('_')
                employee_id = parts[1]
                shift_number = int(parts[2])
                if employee_id not in assignments:
                    assignments[employee_id] = []
                assignments[employee_id].append(shift_number)
        return Schedule(assignments)

    @staticmethod
    def add_hard_constraints(
            required_nurse_hprd_count: HprdShiftNurseRequirements,
            shifts: List[Shift],
            nurse_roles: List[NurseRole],
            nurses: List[NurseProfile],
            problem: LpProblem,
            lp_variables_holder: LpNurseShiftVariableHolder,
            check_nurse_can_cover_shift_func: INurseCanCoverShiftFunc,
    ) -> None:
        """Mandatory constraints from FacilityConfig and staffing laws."""

        # 1. HPRD Coverage (The Core Constraint)
        for shift in shifts:
            for nurse_role in nurse_roles:
                required_count = required_nurse_hprd_count[shift, nurse_role]
                if required_count > 0:
                    total_staffed_nurses = sum(
                        lp_variables_holder.get_variable(n.employee_id, shift.shift_id)
                        for n in nurses
                        if n.role == nurse_role and check_nurse_can_cover_shift_func(n, shift)
                    )
                    problem += total_staffed_nurses >= required_count, \
                        f"HPRD_Min_Nurse_Count_{shift.shift_id}_{nurse_role}"

        # 2. Fatigue/Rest Constraint (Example)
        # Ensure no nurse works consecutive shifts without adequate rest.
        for nurse in nurses:
            for i in range(len(shifts) - 1):
                current_shift = shifts[i]
                next_shift = shifts[i + 1]
                problem += (
                    lp_variables_holder.get_variable(nurse.employee_id, current_shift.shift_id)
                    + lp_variables_holder.get_variable(nurse.employee_id, next_shift.shift_id) <= 1,
                    f"Fatigue_{nurse.employee_id}_{current_shift.shift_id}"
                )

    @staticmethod
    def set_objective_function(
            shifts: List[Shift],
            nurses: List[NurseProfile],
            var_holder: LpNurseShiftVariableHolder,
            preference_weights: PreferenceWeights,
            problem: LpProblem,
            shift_cost_calculator: IShiftCostCalculator,
            model_outputs: MlModelOutputs,
            calculate_preference_penalty: IPreferencePenaltyCalculator,
    ) -> LpProblem:
        """Sets the objective: Minimize cost while penalizing soft constraint violations.
        """
        total_cost_expression = []

        for nurse in nurses:

            turnover_risk = model_outputs.turnover_risk_scores.get(nurse.employee_id, 0.0)

            for shift in shifts:

                var = var_holder.get_variable(nurse.employee_id, shift.shift_id)
                cost = shift_cost_calculator(nurse, shift)  # Includes OT/Agency multipliers

                # Add preference penalties as a weighted cost
                penalty_cost = calculate_preference_penalty(nurse, shift, preference_weights)

                if turnover_risk > 0.0:
                    penalty_cost += turnover_risk * preference_weights.high_risk_shift_penalty

                total_cost_expression += (cost + penalty_cost) * var

        problem += (
            sum(total_cost_expression),
            "Total_Weighted_Cost"
        )

        return problem

    @staticmethod
    def build_problem() -> LpProblem:
        return LpProblem("Optimal_Schedule", LpMinimize)

    @staticmethod
    def add_lp_variable_per_nurse_shift(
            nurses: List[NurseProfile],
            shifts: List[Shift],
            lp_variable_holder: LpNurseShiftVariableHolder,
    ) -> None:
        for nurse in nurses:
            for shift in shifts:
                lp_variable_holder.add_variable(
                    nurse.employee_id,
                    shift.shift_id
                )

    # =======================================================
    # ESSENTIAL HELPER METHODS
    # =======================================================

    @staticmethod
    def _calculate_hprd_shift_role_req_hours(
            residents: List[ResidentAcuity],
            shifts: List[Shift],
            config: FacilityConfig,
            shift_requirements: ShiftSpecificRequirements,
            min_mandate: MinMandates,
    ) -> HprdShiftNurseRequirements:
        """
        Calculates the acuity-adjusted mandated nursing hours (HPRD) required
        for each unit and shift across all shifts in the forecast horizon.

        # Output: {('Shift_1_RN', Shift(...)): 12.5, ('Shift_2_CNA', Shift(...)): 50.0, ...}
        """
        total_census = len(residents)

        # Placeholder for complex Acuity-to-HPRD conversion (Your core IP)
        # This function would call predictive_ml._calculate_required_minutes(resident)
        # for each resident and aggregate by unit/shift.

        req_vals = np.zeros(
            (
                len(shifts),
                len(NurseRole)
            )
        )

        for shift_idx, shift in enumerate(shifts):
            hours_in_shift = (shift.shift_end_time - shift.shift_start_time).total_hours()

            # Use FacilityConfig mandates
            required_rn_hours = shift_requirements.target_hprd_rn * total_census
            required_lpn_hours = shift_requirements.target_hprd_lpn * total_census
            required_cna_hours = shift_requirements.target_hprd_cna * total_census

            # Convert HPRD (per resident day) to Hours per shift
            required_rn_shift_hours = required_rn_hours / hours_in_shift
            required_lpn_shift_hours = required_lpn_hours / hours_in_shift
            required_cna_shift_hours = required_cna_hours / hours_in_shift

            req_vals[shift_idx, 0] = required_rn_shift_hours
            req_vals[shift_idx, 1] = required_lpn_shift_hours
            req_vals[shift_idx, 2] = required_cna_shift_hours

        return HprdShiftNurseRequirements(
            values=req_vals,
            shifts=shifts,
            roles=[NurseRole.RN, NurseRole.LPN, NurseRole.CNA]
        )

    @staticmethod
    def is_weekend(day_of_week: DayOfWeek) -> bool:
        """Helper to determine if a given day is a weekend."""
        return day_of_week in {DayOfWeek.SATURDAY, DayOfWeek.SUNDAY}

    @staticmethod
    def _nurse_can_cover_shift(nurse: NurseProfile, shift: Shift) -> bool:
        """
        Checks all HARD BLOCKERS (time off requests, skill gaps, max hours).
        If False, the nurse cannot be assigned to this variable.
        """
        # Check 1: Mandatory time off blocks (from StaffPreference)
        if ScheduleOptimizer._is_hard_block(nurse, shift):
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
                        if ScheduleOptimizer.is_weekend(shift.day_of_week):
                            return True
        return False
