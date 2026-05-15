import asyncio
import logging
import math
import time

import pulp
import whenever
from pulp import LpMinimize, LpProblem

from snf_schedule_optimizer.models import DomainPrimaryKeyType, PreferenceWeights
from snf_schedule_optimizer.optimizer.context import (
    LpNurseShiftVariableHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    IObjectivePenaltyStrategy,
    IPayModelStrategy,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.optimizer.models import (
    InfeasibilityReason,
    InfeasibilityReasonResult,
    ScheduleOptimizationResults,
    ScheduleOptimizationStats,
)
from snf_schedule_optimizer.optimizer.schedule_extraction import ScheduleExtractor
from snf_schedule_optimizer.optimizer.strategies.variables import (
    CoreVariableGenerationStrategy,
)
from snf_schedule_optimizer.solver import CbcSolverAdapter, SolverAdapter

logger = logging.getLogger(__name__)


class NurseShiftScheduleOptimizer:
    """
    Formulates and solves the Acuity-Driven Nurse Scheduling ILP.

    - Using retrievers to handle simulation and real time data in same engine.
    """

    def __init__(
        self,
        # provider_factory removed; injected dependencies are now pure strategies/logic
        core_variable_strategy: CoreVariableGenerationStrategy,
        global_pay_strategies: list[IPayModelStrategy],
        facility_constraint_strategies: list[IFacilityScopedConstraintStrategy],
        facility_rule_strategies: list[IFacilityScopedConstraintStrategy],
        penalty_strategies: list[IObjectivePenaltyStrategy],
        solver_adapter: SolverAdapter | None = None,
    ) -> None:
        self.core_variable_strategy = core_variable_strategy

        self.global_pay_strategies = global_pay_strategies
        self.facility_constraint_strategies = facility_constraint_strategies
        self.facility_rule_strategies = facility_rule_strategies
        self.penalty_strategies = penalty_strategies
        self.solver_adapter = solver_adapter or CbcSolverAdapter()

        # Internal helper
        self._extractor = ScheduleExtractor()

    async def solve(
        self,
        data_provider: IScenarioDataProvider,
        preference_weights: PreferenceWeights,
    ) -> ScheduleOptimizationResults:
        t_start = time.perf_counter()
        problem = LpProblem("Scheduling", LpMinimize)
        lp_vars = LpNurseShiftVariableHolder()

        facility_ids = data_provider.get_facility_ids()
        all_shifts = data_provider.get_all_shifts()
        logger.info(
            "Model build started: %d facilities, %d shifts",
            len(facility_ids),
            len(all_shifts),
        )

        # --- Phase 1: Variable Creation ---
        t_phase = time.perf_counter()

        for pay_strategy in self.global_pay_strategies:
            await pay_strategy.create_variables(lp_vars, data_provider)

        for facility_id in facility_ids:
            await self.core_variable_strategy.create_variables(
                lp_vars,
                data_provider,
                facility_id,
            )

        logger.info(
            "Variables created: %d (phase %.2fs, total %.2fs)",
            problem.numVariables(),
            time.perf_counter() - t_phase,
            time.perf_counter() - t_start,
        )

        # --- Phase 2: Constraints ---
        t_phase = time.perf_counter()

        for facility_id in facility_ids:
            for rule_strategy in self.facility_rule_strategies:
                infeasibility = await rule_strategy.apply_constraints(
                    problem, lp_vars, data_provider, facility_id
                )
                if infeasibility is not None:
                    return self._early_infeasibility(infeasibility, problem)

            for constraint_strategy in self.facility_constraint_strategies:
                infeasibility = await constraint_strategy.apply_constraints(
                    problem, lp_vars, data_provider, facility_id
                )
                if infeasibility is not None:
                    return self._early_infeasibility(infeasibility, problem)

        for pay_strategy in self.global_pay_strategies:
            await pay_strategy.apply_constraints(
                problem, lp_vars, data_provider
            )

        logger.info(
            "Constraints applied: V=%d C=%d (phase %.2fs, total %.2fs)",
            problem.numVariables(),
            problem.numConstraints(),
            time.perf_counter() - t_phase,
            time.perf_counter() - t_start,
        )

        # --- Phase 3: Objective Function ---
        t_phase = time.perf_counter()

        obj_terms = []
        for pay_strategy in self.global_pay_strategies:
            obj_terms.extend(
                await pay_strategy.get_objective_terms(lp_vars, data_provider)
            )

        for penalty_strategy in self.penalty_strategies:
            obj_terms.extend(
                await penalty_strategy.get_penalty_terms(
                    lp_vars, data_provider, preference_weights
                )
            )

        problem += pulp.lpSum(obj_terms)

        logger.info(
            "Objective built: %d terms C=%d (phase %.2fs, total %.2fs)",
            len(obj_terms),
            problem.numConstraints(),
            time.perf_counter() - t_phase,
            time.perf_counter() - t_start,
        )

        org_id = data_provider.get_org_id()
        holiday_dates: dict[int, set[whenever.Date]] = {}
        for fid in data_provider.get_facility_ids():
            config = data_provider.get_facility_config(fid)
            if config.holiday_dates:
                holiday_dates[fid] = set(config.holiday_dates)

        logger.info(
            "CBC solver started V=%d C=%d (timeout=%ds)",
            problem.numVariables(),
            problem.numConstraints(),
            getattr(self.solver_adapter, "time_limit_seconds", 60),
        )
        return await asyncio.to_thread(
            self._solve_finalize,
            org_id,
            problem,
            lp_vars,
            holiday_dates,
        )

    def _early_infeasibility(
        self,
        infeasibility: InfeasibilityReasonResult,
        problem: pulp.LpProblem,
    ) -> ScheduleOptimizationResults:
        return ScheduleOptimizationResults(
            success=False,
            optimal_schedule=None,
            constraint_slacks=None,
            infeasibility_reason=infeasibility,
            statistics=ScheduleOptimizationStats(
                execution_time_ms=0.0,
                total_variables=problem.numVariables(),
                total_constraints=problem.numConstraints(),
                objective_value=None,
            ),
        )

    def _solve_finalize(
        self,
        org_id: DomainPrimaryKeyType,
        problem: pulp.LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        holiday_dates: dict[int, set[whenever.Date]],
    ) -> ScheduleOptimizationResults:
        solver_result = self.solver_adapter.solve(problem)

        logger.info(
            "CBC solve finished: status=%s objective=%.2f elapsed=%.0fms",
            solver_result.status_label,
            solver_result.objective_value or 0.0,
            solver_result.elapsed_ms,
        )

        stats = ScheduleOptimizationStats(
            execution_time_ms=solver_result.elapsed_ms,
            total_variables=problem.numVariables(),
            total_constraints=problem.numConstraints(),
            objective_value=solver_result.objective_value,
        )

        if solver_result.status_code != pulp.LpStatusOptimal:
            infeasibility_reason = InfeasibilityReasonResult(
                InfeasibilityReason.OTHER,
                f"Solver did not find optimal solution. Status: {solver_result.status_label}",
            )
            return ScheduleOptimizationResults(
                False,
                None,
                None,
                infeasibility_reason,
                statistics=stats,
            )

        constraint_slacks = {
            name: constraint.slack
            for name, constraint in problem.constraints.items()
            if constraint.slack is not None
        }

        schedule = self._extractor.extract(
            lp_holder,
            org_id,
            None,
        )

        weekend_distribution: dict[int, int] = {}
        all_values: list[int] = []
        for key, variable in lp_holder.get_all_assignments().items():
            if variable.varValue and variable.varValue > 0.5:
                shift = key.shift
                emp_id = key.employee_id
                if shift.day_of_week == whenever.Weekday.SATURDAY or shift.day_of_week == whenever.Weekday.SUNDAY:
                    weekend_distribution[emp_id] = weekend_distribution.get(emp_id, 0) + 1
                holidays = holiday_dates.get(shift.facility_id, set())
                if shift.shift_start_dt.date() in holidays:
                    weekend_distribution[emp_id] = weekend_distribution.get(emp_id, 0) + 1

        for emp_id in lp_holder.get_all_employees():
            if emp_id not in weekend_distribution:
                weekend_distribution[emp_id] = 0

        all_counts = list(weekend_distribution.values())
        fairness_score = 100.0
        if len(all_counts) > 1:
            avg = sum(all_counts) / len(all_counts)
            variance = sum((c - avg) ** 2 for c in all_counts) / len(all_counts)
            std_dev = math.sqrt(variance)
            if avg > 0:
                fairness_score = 100.0 * (1.0 - std_dev / avg)
                fairness_score = max(0.0, min(100.0, fairness_score))

        return ScheduleOptimizationResults(
            success=True,
            optimal_schedule=schedule,
            constraint_slacks=constraint_slacks,
            infeasibility_reason=None,
            statistics=stats,
            weekend_assignment_distribution=weekend_distribution,
            fairness_score=fairness_score,
        )
