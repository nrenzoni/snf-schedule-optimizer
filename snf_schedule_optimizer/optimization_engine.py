import abc

from snf_schedule_optimizer.data_models.main_data_models import *
import pulp
from pulp import LpProblem, LpMinimize, LpVariable, LpBinary
from dataclasses import dataclass


@dataclass(frozen=True)
class PreferenceWeights:
    night_shift_penalty_weight: float = 500.0
    ot_avoidance_penalty: float = 1000.0
    team_consistency_penalty: float = 300.0
    high_risk_shift_penalty: float = 2000.0


@dataclass(frozen=True)
class Shift:
    shift_number: int
    day_shift: bool
    day_of_week: DayOfWeek


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

    def add_variable(self, employee_id: str, day_shift: int) -> LpVariable:
        var_name = f"X_{employee_id}_{day_shift}"
        var = LpVariable(var_name, cat=LpBinary)
        self.variables[var_name] = var
        return var

    def get_variable(self, employee_id: str, day_shift: int) -> LpVariable:
        var_name = f"X_{employee_id}_{day_shift}"
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
                penalty += preference_weights.night_shift_penalty_weight

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
        base_cost = nurse.hourly_cost_base * 8

        # Logic to apply premium multipliers
        if nurse.is_agency:
            return base_cost * nurse.ot_multiplier  # Agency cost (e.g., 2.2x)

        # Logic for mandatory overtime (e.g., beyond 40 hours/week or certain shifts)
        # For simplicity, we mock a premium for weekend shifts (shift 6, 7, 13, 14 are examples)
        if ScheduleOptimizer.is_weekend(shift.day_of_week):
            return base_cost * 1.25  # Mock 25% shift differential for weekends

        return base_cost


@dataclass(frozen=True)
class ScheduleOptimizationParams:
    pass


@dataclass(frozen=True)
class ScheduleOptimizationResults:
    success: bool
    optimal_schedule: Optional[Schedule]  # {variable_name: value}


# 14 day optimization, i.e., 2 weeks ahead
class ScheduleOptimizer:
    """Formulates and solves the Acuity-Driven Nurse Scheduling ILP."""

    @staticmethod
    def solve(
            nurses: List[NurseProfile],
            residents: List[ResidentAcuity],
            shifts: List[Shift],
            facility_params: FacilityConfig,
            min_mandates: List[MinMandates],
            preference_weights: PreferenceWeights,
            shift_requirements: ShiftSpecificRequirements,
            model_outputs: MlModelOutputs,
    ) -> ScheduleOptimizationResults:
        """
        Executes the solver and returns the optimized schedule.
        """
        problem = ScheduleOptimizer.build_problem()
        lp_vars_holder = LpNurseShiftVariableHolder()
        ScheduleOptimizer.add_lp_variables_nurse_constraints(nurses, lp_vars_holder)
        acuity_hours = ScheduleOptimizer._calculate_acuity_hours(residents, facility_params, shift_requirements)
        ScheduleOptimizer.add_hard_constraints(acuity_hours, nurses, problem, lp_vars_holder, NurseCanCoverShiftImpl())

        problem = ScheduleOptimizer.set_objective_function(
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
            acuity_hours: Dict[Tuple[str, Shift], float],
            nurses: List[NurseProfile],
            problem: LpProblem,
            lp_variables_holder: LpNurseShiftVariableHolder,
            check_nurse_can_cover_shift_func: INurseCanCoverShiftFunc,
    ) -> None:
        """Mandatory constraints from FacilityConfig and staffing laws."""
        # 1. Acuity-Based HPRD Coverage (The Core Constraint)
        required_hours = acuity_hours
        for (fac_unit, shift), required_h in required_hours.items():
            total_staffed_hours = sum(
                lp_variables_holder.get_variable(n.employee_id, shift.shift_number) * 8
                for n in nurses
                if check_nurse_can_cover_shift_func(n, shift)  # Check for skills/blocks
            )
            problem += total_staffed_hours >= required_h, f"HPRD_Min_{shift}"

        # 2. Fatigue/Rest Constraint (Example)
        # Ensure no nurse works consecutive shifts without adequate rest.
        for nurse in nurses:
            for day in range(1, N_FORECAST_AHEAD_DAYS):
                # If they work shift 1, they cannot work shift 2 (simplified)
                problem += (
                    lp_variables_holder.get_variable(nurse.employee_id, day)
                    + lp_variables_holder.get_variable(nurse.employee_id, day + 1) <= 1,
                    f"Fatigue_{nurse.employee_id}_{day}"
                )

    @staticmethod
    def set_objective_function(
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
        # assume every 3rd shift is night
        shifts = [Shift(
            shift_number=i,
            day_shift=(i % 3 != 0),
            day_of_week=DayOfWeek((i - 1) % 7 + 1),  # 1=Mon, 7=Sun
        )
            for i in range(1, N_FORECAST_AHEAD_DAYS + 1)
        ]
        for nurse in nurses:

            turnover_risk = model_outputs.turnover_risk_scores.get(nurse.employee_id, 0.0)

            for shift in shifts:

                var = var_holder.get_variable(nurse.employee_id, shift.shift_number)
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
    def add_lp_variables_nurse_constraints(
            nurses: List[NurseProfile],
            lp_variable_holder: LpNurseShiftVariableHolder,
    ) -> None:
        for nurse in nurses:
            for day_shift in range(1, N_FORECAST_AHEAD_DAYS):
                lp_variable_holder.add_variable(nurse.employee_id, day_shift)

    # =======================================================
    # ESSENTIAL HELPER METHODS
    # =======================================================

    @staticmethod
    def _calculate_acuity_hours(
            residents: List[ResidentAcuity],
            config: FacilityConfig,
            shift_requirements: ShiftSpecificRequirements,
    ) -> Dict[Tuple[str, Shift], float]:
        """
        Calculates the acuity-adjusted mandated nursing hours (HPRD) required
        for each unit and shift across the 14-day schedule.

        # Output: {('Shift_1_RN', Shift(...)): 12.5, ('Shift_2_CNA', Shift(...)): 50.0, ...}
        """
        required_hours: Dict[Tuple[str, Shift], float] = {}
        total_census = len(residents)

        # Placeholder for complex Acuity-to-HPRD conversion (Your core IP)
        # This function would call predictive_ml._calculate_required_minutes(resident)
        # for each resident and aggregate by unit/shift.

        for day_shift in range(1, N_FORECAST_AHEAD_DAYS + 1):
            shift = Shift(
                shift_number=day_shift,
                day_shift=True,  # Simplification: Assume all day shifts for this example
                day_of_week=DayOfWeek((day_shift - 1) % 7 + 1),  # 1=Mon, 7=Sun
            )
            # Simplified mock logic based on total census and facility mandated HPRD
            hours_per_shift = 8

            # Use FacilityConfig mandates
            required_rn_hours = shift_requirements.target_hprd_rn * total_census
            required_lpn_hours = shift_requirements.target_hprd_lpn * total_census
            required_cna_hours = shift_requirements.target_hprd_cna * total_census

            # Convert HPRD (per resident day) to Hours per shift
            required_rn_shift_hours = required_rn_hours / config.shifts_per_day
            required_lpn_shift_hours = required_lpn_hours / config.shifts_per_day
            required_cna_shift_hours = required_cna_hours / config.shifts_per_day

            required_hours[f"RN_{day_shift}", shift] = required_rn_shift_hours
            required_hours[f"LPN_{day_shift}", shift] = required_lpn_shift_hours
            required_hours[f"CNA_{day_shift}", shift] = required_cna_shift_hours

        return required_hours

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
