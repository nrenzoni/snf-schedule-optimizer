import pulp
import whenever
from pulp import LpProblem

from snf_schedule_optimizer.domain.hr.interfaces import IEmployeeRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IPreferencePenaltyProcessor,
)
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    PreferenceWeights,
    Shift,
)
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    IObjectivePenaltyStrategy,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.optimizer.lp_helpers import build_lp_variable_name
from snf_schedule_optimizer.optimizer.models import InfeasibilityReasonResult
from snf_schedule_optimizer.persistence import INurseRepo


class QualityOfLifeStrategy(IObjectivePenaltyStrategy):
    def __init__(
        self,
        preference_processor: IPreferencePenaltyProcessor,  # Your existing refactored service
        nurse_retriever: INurseRepo,
        employee_retriever: IEmployeeRepo,
        # ml_model_retriever: IMLModelOutputsRetriever,
    ):
        self.preference_processor = preference_processor
        # self.nurse_retriever = nurse_retriever
        # self.employee_retriever = employee_retriever
        # self.ml_model_retriever = ml_model_retriever

    async def get_penalty_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        weights: PreferenceWeights,
    ) -> list[pulp.LpAffineExpression]:
        penalty_terms = []
        settings = data_provider.get_optimization_settings()
        assignments_by_employee: dict[int, list[tuple[Shift, pulp.LpVariable]]] = {}

        for shift in data_provider.get_all_shifts():
            # Get Context
            ml_outputs = data_provider.get_ml_model_outputs(shift)
            nurses = await data_provider.get_nurses_for_shift(shift)

            for nurse in nurses:
                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                lp_var = lp_holder.get_variable(
                    shift,
                    nurse.employee_id,
                )
                if lp_var is None:
                    continue

                assignments_by_employee.setdefault(nurse.employee_id, []).append(
                    (shift, lp_var)
                )

                # 1. Calculate Preference Penalty (The "Soft" Constraints)
                # (Delegates to your service from Turn 2)
                accumulated = await data_provider.get_accumulated_hours_for_pay_period(
                    nurse.employee_id
                )
                pref_penalty = await self.preference_processor.calculate_penalty_cost(
                    employee, nurse, shift, weights, accumulated_hours=accumulated
                )

                # 2. Calculate Turnover Risk Penalty
                # (High risk nurses shouldn't be placed in "bad" shifts if possible)
                risk_score = ml_outputs.turnover_risk_scores.get(nurse.employee_id, 0.0)
                risk_penalty = 0.0
                if risk_score > 0.0:
                    # Simple logic: High risk * Configured Weight
                    risk_penalty = risk_score * weights.high_risk_shift_penalty

                if settings.use_ml_forecast:
                    risk_penalty += (
                        ml_outputs.shift_call_out_forecast
                        * weights.high_risk_shift_penalty
                    )

                # 3. Add to list
                total_penalty = pref_penalty + risk_penalty
                if total_penalty > 0:
                    penalty_terms.append(lp_var * total_penalty)

        for employee_assignments in assignments_by_employee.values():
            if len(employee_assignments) < 2:
                continue
            employee_assignments.sort(key=lambda item: item[0].shift_start_dt)
            previous_shift = employee_assignments[0][0]
            for shift, lp_var in employee_assignments[1:]:
                if shift.unit_id != previous_shift.unit_id:
                    penalty_terms.append(lp_var * weights.team_consistency_penalty)
                previous_shift = shift

        return penalty_terms


class WeekendFairnessPenaltyStrategy(
    IObjectivePenaltyStrategy, IFacilityScopedConstraintStrategy
):
    def __init__(self) -> None:
        self._deviation_vars: dict[str, tuple[pulp.LpVariable, pulp.LpVariable]] = {}
        self._constraints_added = False

    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        if self._constraints_added:
            return None

        shifts = data_provider.get_all_shifts()
        if not shifts:
            self._constraints_added = True
            return None

        nurses_by_id: dict[int, list[tuple[Shift, pulp.LpVariable]]] = {}
        for shift in shifts:
            for nurse in await data_provider.get_nurses_for_shift(shift):
                v = lp_holder.get_variable(shift, nurse.employee_id)
                if v is not None:
                    nurses_by_id.setdefault(nurse.employee_id, []).append((shift, v))

        num_nurses = len(nurses_by_id)
        if num_nurses < 2:
            self._constraints_added = True
            return None

        facility_configs: dict[int, set[whenever.Date]] = {}
        for fid in data_provider.get_facility_ids():
            config = data_provider.get_facility_config(fid)
            if config.holiday_dates:
                facility_configs[fid] = set(config.holiday_dates)

        weekend_vars: dict[int, list[pulp.LpVariable]] = {}
        holiday_vars: dict[int, list[pulp.LpVariable]] = {}
        for emp_id, shift_var_list in nurses_by_id.items():
            weekend_vars[emp_id] = []
            holiday_vars[emp_id] = []
            for shift, var in shift_var_list:
                if (
                    shift.day_of_week == whenever.Weekday.SATURDAY
                    or shift.day_of_week == whenever.Weekday.SUNDAY
                ):
                    weekend_vars[emp_id].append(var)
                holidays = facility_configs.get(shift.facility_id, set())
                if shift.shift_start_dt.date() in holidays:
                    holiday_vars[emp_id].append(var)

        if weekend_vars:
            self._add_deviation_constraints(
                problem, weekend_vars, num_nurses, "WeekendFairness"
            )
        if holiday_vars:
            self._add_deviation_constraints(
                problem, holiday_vars, num_nurses, "HolidayFairness"
            )

        self._constraints_added = True
        return None

    def _add_deviation_constraints(
        self,
        problem: LpProblem,
        nurse_shift_vars: dict[int, list[pulp.LpVariable]],
        num_nurses: int,
        label: str,
    ) -> None:
        nurse_counts: dict[int, pulp.LpAffineExpression] = {
            emp_id: pulp.lpSum(vars) for emp_id, vars in nurse_shift_vars.items()
        }
        total_count = pulp.lpSum(nurse_counts.values())
        avg_count = total_count / num_nurses

        for emp_id, count_expr in nurse_counts.items():
            p_var = pulp.LpVariable(
                build_lp_variable_name(label, "P", emp_id),
                lowBound=0,
                cat=pulp.LpContinuous,
            )
            n_var = pulp.LpVariable(
                build_lp_variable_name(label, "N", emp_id),
                lowBound=0,
                cat=pulp.LpContinuous,
            )
            self._deviation_vars[f"{label}:{emp_id}"] = (p_var, n_var)
            problem += (
                count_expr - avg_count == p_var - n_var,
                build_lp_variable_name(label, "Dev", emp_id),
            )

    async def get_penalty_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        weights: PreferenceWeights,
    ) -> list[pulp.LpAffineExpression]:
        penalty_terms: list[pulp.LpAffineExpression] = []

        weekend_weight = weights.weekend_fairness_penalty
        holiday_weight = weights.holiday_fairness_penalty

        for key, (p_var, n_var) in self._deviation_vars.items():
            if key.startswith("WeekendFairness:") and weekend_weight > 0:
                penalty_terms.append((p_var + n_var) * weekend_weight)
            elif key.startswith("HolidayFairness:") and holiday_weight > 0:
                penalty_terms.append((p_var + n_var) * holiday_weight)

        return penalty_terms
