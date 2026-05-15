import pulp

from snf_schedule_optimizer.domain.hr.interfaces import IEmployeeRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IPreferencePenaltyProcessor,
)
from snf_schedule_optimizer.models import PreferenceWeights, Shift
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import (
    IObjectivePenaltyStrategy,
    IScenarioDataProvider,
)
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

                assignments_by_employee.setdefault(nurse.employee_id, []).append((shift, lp_var))

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
