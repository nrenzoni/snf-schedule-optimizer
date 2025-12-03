from dataclasses import dataclass

import pendulum

from snf_schedule_optimizer.models import PreferenceWeights, Schedule
from snf_schedule_optimizer.models.scheduling.schedule_cost_models import (
    ScheduleFinancialReport,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.diagnostics import SchedulerInfeasibilityDiagnoser
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.models import ScheduleOptimizationStats
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.reporting import (
    ScheduleAnalysisReport,
    ScheduleResultAnalyzer,
)
from snf_schedule_optimizer.schedule_cost_evaluator import ScheduleCostEvaluator


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
    ):
        self.provider_factory = provider_factory
        self.optimizer = optimizer
        self.cost_evaluator = cost_evaluator

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
        # Note: You will need to update optimizer.solve signature to accept data_provider
        result = self.optimizer.solve(
            data_provider=data_provider,
            preference_weights=preference_weights,
        )

        if not result.success or not result.optimal_schedule:
            # --- START DIAGNOSTICS ---
            error_msg = str(result.infeasibility_reason)

            # Since we have the provider context, we can run the diagnostics
            diagnoser = SchedulerInfeasibilityDiagnoser(data_provider)
            diagnostic_report = diagnoser.generate_report_string()

            # Append diagnostics to the error details
            full_error_details = f"{error_msg}\n{diagnostic_report}"

            # Print to stdout for developer visibility during tests/debug
            print(diagnostic_report)
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
        # We reuse the SAME data_provider instance.
        analyzer = ScheduleResultAnalyzer(data_provider)
        analysis_report = analyzer.analyze(result.optimal_schedule)

        # 4. Run Financial Reporting (Costs)
        # We reuse the SAME data_provider instance.
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
