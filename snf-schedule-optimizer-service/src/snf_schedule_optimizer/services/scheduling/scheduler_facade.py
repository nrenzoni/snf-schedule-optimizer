import copy
from dataclasses import dataclass

import pendulum

from api.dtos import MoveEmployeeRequest
from snf_schedule_optimizer.models import PreferenceWeights, Schedule
from snf_schedule_optimizer.models.scheduling.schedule_cost_models import (
    ScheduleFinancialReport,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.diagnostics import SchedulerInfeasibilityDiagnoser
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.optimizer.models import (
    ScheduleOptimizationResults,
    ScheduleOptimizationStats,
)
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.reporting import (
    ScheduleAnalysisReport,
    ScheduleResultAnalyzer,
)
from snf_schedule_optimizer.optimizer.strategies.fixing import (
    PinnedScheduleConstraintStrategy,
)
from snf_schedule_optimizer.schedule_cost_evaluator import ScheduleCostEvaluator
from snf_schedule_optimizer.services.scheduling.interfaces import IScheduleRetriever


@dataclass(frozen=True)
class OptimizationOutput:
    """The complete package returned to the client."""

    is_success: bool
    schedule: Schedule | None
    analysis: ScheduleAnalysisReport | None
    financials: ScheduleFinancialReport | None
    stats: ScheduleOptimizationStats | None
    error_details: str | None = None


class WorkforceSchedulerService:
    """
    High-Level Facade that coordinates the optimization pipeline.
    Client code calls this, not the engine directly.
    """

    def __init__(
        self,
        provider_factory: ScenarioDataProviderFactory,
        optimizer: NurseShiftScheduleOptimizer,
        cost_evaluator: ScheduleCostEvaluator,
        schedule_retriever: IScheduleRetriever,
    ):
        self.provider_factory = provider_factory
        self.optimizer = optimizer
        self.cost_evaluator = cost_evaluator
        self.schedule_retriever = schedule_retriever

    def optimize_schedule(
        self,
        org_id: str,
        facility_contexts: dict[str, FacilityScenarioContext],
        preference_weights: PreferenceWeights,
        pay_period_start: pendulum.DateTime,
        optimization_start_time: pendulum.DateTime | None = None,
    ) -> OptimizationOutput:
        # should never be after data in the provider.
        # todo: add check somewhere that no history data is after this time
        optimization_start_time = (
            optimization_start_time if optimization_start_time else pendulum.now()
        )

        # 1. Create the Data Provider Scope (Outside the Engine)
        # This ensures the exact same data cache is used for Optimization AND Reporting.
        data_provider = self.provider_factory.create(
            org_id=org_id,
            facility_contexts=facility_contexts,
            pay_period_start=pay_period_start,
            optimization_start_time=optimization_start_time,
        )

        # 2. Run Optimization (Injecting the Provider)
        result = self.optimizer.solve(
            data_provider=data_provider,
            preference_weights=preference_weights,
        )

        return self._process_results(result, data_provider)

    def validate_shift_move(
        self,
        facility_contexts: dict[str, FacilityScenarioContext],
        move_request: MoveEmployeeRequest,
        pay_period_start: pendulum.DateTime,
    ) -> OptimizationOutput:
        """
        Validates if a specific move (drag & drop) is feasible against all rules.
        Retrieves the current schedule state from persistence to ensure accuracy.
        """
        org_id = move_request.org_id
        schedule_id = move_request.schedule_id

        current_schedule = self.schedule_retriever.get_schedule(
            schedule_id,
            org_id,
        )

        if not current_schedule:
            return OptimizationOutput(
                is_success=False,
                schedule=None,
                analysis=None,
                financials=None,
                stats=None,
                error_details=f"Schedule {schedule_id} not found for org {org_id}",
            )

        # 1. Mutate Schedule In-Memory (The "What-If" State)
        proposed_schedule = copy.deepcopy(current_schedule)
        self._apply_move_to_schedule(
            proposed_schedule,
            move_request,
        )

        # 2. Create a Pinned Optimizer
        # We clone the existing optimizer's logic but add the "Pinning" constraint
        # which forces the solver to evaluate ONLY this specific schedule state.
        pinning_strategy = PinnedScheduleConstraintStrategy(proposed_schedule)

        validator_optimizer = NurseShiftScheduleOptimizer(
            core_variable_strategy=self.optimizer.core_variable_strategy,
            global_pay_strategies=self.optimizer.global_pay_strategies,
            # Inject Pinning Strategy to force the solver to check ONLY this configuration
            facility_constraint_strategies=(
                self.optimizer.facility_constraint_strategies + [pinning_strategy]
            ),
            facility_rule_strategies=self.optimizer.facility_rule_strategies,
            penalty_strategies=self.optimizer.penalty_strategies,
        )

        # 3. Create Data Provider
        data_provider = self.provider_factory.create(
            org_id=org_id,
            facility_contexts=facility_contexts,
            pay_period_start=pay_period_start,
            optimization_start_time=pendulum.now(),
        )

        # 4. Solve (Validation)
        # We pass default weights because we primarily care about Feasibility here
        result = validator_optimizer.solve(
            data_provider=data_provider,
            preference_weights=PreferenceWeights(),
        )

        return self._process_results(result, data_provider)

    def _process_results(
        self,
        result: ScheduleOptimizationResults,
        data_provider: IScenarioDataProvider,
    ) -> OptimizationOutput:
        """Shared logic for processing results into the output format."""
        if not result.success or not result.optimal_schedule:
            # --- START DIAGNOSTICS ---
            error_msg = str(result.infeasibility_reason)

            # Since we have the provider context, we can run the diagnostics
            diagnoser = SchedulerInfeasibilityDiagnoser(data_provider)
            diagnostic_report = diagnoser.generate_report_string()

            # Append diagnostics to the error details
            full_error_details = f"{error_msg}\n{diagnostic_report}"

            # Print to stdout for developer visibility during tests/debug
            # print(diagnostic_report)
            # --- END DIAGNOSTICS ---

            return OptimizationOutput(
                is_success=False,
                schedule=None,
                analysis=None,
                financials=None,
                stats=result.statistics,
                error_details=full_error_details,
            )

        # 3. Run Analysis (Constraints, Preferences, Compliance)
        analyzer = ScheduleResultAnalyzer(data_provider)
        analysis_report = analyzer.analyze(result.optimal_schedule)

        # 4. Run Financial Reporting (Costs)
        financial_report = self.cost_evaluator.evaluate_schedule(
            result.optimal_schedule, data_provider
        )

        # 5. Return Composite Result
        return OptimizationOutput(
            is_success=True,
            schedule=result.optimal_schedule,
            analysis=analysis_report,
            financials=financial_report,
            stats=result.statistics,
        )

    def _apply_move_to_schedule(
        self,
        schedule: Schedule,
        request: MoveEmployeeRequest,
    ) -> None:
        """Applies the delta to the schedule object in place."""
        if request.from_shift_id == request.to_shift_id:
            # No-op if moving within the same shift
            return
        if not request.from_shift_id and not request.to_shift_id:
            raise ValueError("Both from_shift_id and to_shift_id cannot be None.")

        # Remove from old shift
        if request.from_shift_id:
            from_shift_assigned = next(
                (
                    assigned
                    for (shift_id, assigned) in schedule.shift_assignments.items()
                    if shift_id == request.from_shift_id
                ),
                None,
            )
            if from_shift_assigned is None:
                raise ValueError(
                    f"Shift {request.from_shift_id} not found in schedule."
                )
            if request.employee_id in from_shift_assigned:
                from_shift_assigned.remove(request.employee_id)

        # Add to new shift
        if request.to_shift_id:
            to_shift_assigned = next(
                (
                    assigned
                    for (shift_id, assigned) in schedule.shift_assignments.items()
                    if shift_id == request.to_shift_id
                ),
                None,
            )
            if to_shift_assigned is None:
                raise ValueError(f"Shift {request.to_shift_id} not found in schedule.")
            if request.employee_id not in to_shift_assigned:
                to_shift_assigned.append(request.employee_id)
