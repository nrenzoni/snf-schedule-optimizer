from collections import defaultdict

import pendulum
import pulp
from pulp import LpMinimize, LpProblem

from snf_schedule_optimizer.models import PreferenceWeights, Schedule
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    LpNurseShiftVariableHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    IObjectivePenaltyStrategy,
    IPayModelStrategy,
)
from snf_schedule_optimizer.optimizer.models import (
    InfeasibilityReason,
    InfeasibilityReasonResult,
    ScheduleOptimizationResults,
)
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.variables import (
    CoreVariableGenerationStrategy,
)


class NurseShiftScheduleOptimizer:
    """
    Formulates and solves the Acuity-Driven Nurse Scheduling ILP.

    - Using retrievers to handle simulation and real time data in same engine.
    """

    def __init__(
        self,
        provider_factory: ScenarioDataProviderFactory,
        core_variable_strategy: CoreVariableGenerationStrategy,
        global_pay_strategies: list[IPayModelStrategy],
        facility_constraint_strategies: list[IFacilityScopedConstraintStrategy],
        facility_rule_strategies: list[IFacilityScopedConstraintStrategy],
        penalty_strategies: list[IObjectivePenaltyStrategy],
    ) -> None:
        self.provider_factory = provider_factory
        self.core_variable_strategy = core_variable_strategy

        self.global_pay_strategies = global_pay_strategies
        self.facility_constraint_strategies = facility_constraint_strategies
        self.facility_rule_strategies = facility_rule_strategies
        self.penalty_strategies = penalty_strategies

    def solve(
        self,
        org_id: str,
        preference_weights: PreferenceWeights,
        facility_contexts: dict[str, FacilityScenarioContext],
        pay_period_start: pendulum.DateTime,
        optimization_start_time: pendulum.DateTime | None = None,
    ) -> ScheduleOptimizationResults:
        # 1. Infer Optimization Start if not provided
        # If the caller doesn't say when the optimization starts, assume it starts
        # at the moment of the earliest shift in the list.
        if optimization_start_time is None:
            if not any(f.shifts for f in facility_contexts.values()):
                return ScheduleOptimizationResults(
                    False,
                    None,
                    None,
                    InfeasibilityReasonResult(
                        InfeasibilityReason.OTHER, "No shifts provided"
                    ),
                )
            optimization_start_time = min(
                s.shift_start_dt
                for fac in facility_contexts.values()
                for s in fac.shifts
            )

        data_provider = self.provider_factory.create(
            org_id=org_id,
            facility_contexts=facility_contexts,
            pay_period_start=pay_period_start,
            optimization_start_time=optimization_start_time,
        )

        problem = LpProblem("Scheduling", LpMinimize)
        lp_vars = LpNurseShiftVariableHolder()

        facility_ids = data_provider.get_facility_ids()

        # --- Phase 1: Variable Creation ---

        # A. Global variables (e.g., Pay buckets for employees spanning facilities)
        for pay_strategy in self.global_pay_strategies:
            pay_strategy.create_variables(lp_vars, data_provider)

        # B. Facility-scoped variables (The actual shift assignments)
        for facility_id in facility_ids:
            self.core_variable_strategy.create_variables(
                lp_vars,
                data_provider,
                facility_id,
            )

        # --- Phase 2: Constraints ---

        for facility_id in facility_ids:
            # 1. Apply Rules (e.g. Fatigue, Patterns)
            for rule_strategy in self.facility_rule_strategies:
                rule_strategy.apply_constraints(
                    problem, lp_vars, data_provider, facility_id
                )

            # 2. Apply Constraints (e.g. HPRD, Min Staffing)
            for constraint_strategy in self.facility_constraint_strategies:
                constraint_strategy.apply_constraints(
                    problem, lp_vars, data_provider, facility_id
                )

        # Apply Global Constraints (Pay/OT linkage across facilities)
        for pay_strategy in self.global_pay_strategies:
            pay_strategy.apply_constraints(problem, lp_vars, data_provider)  # OT Math

        # --- Phase 3: Objective Function ---

        obj_terms = []
        # Pay is usually global
        for pay_strategy in self.global_pay_strategies:
            obj_terms.extend(pay_strategy.get_objective_terms(lp_vars, data_provider))

        # Penalties might need facility scoping if weights differ per facility,
        # but usually iterating over all shifts globally is fine for preferences.
        # If needed, loop through facilities here too.
        for penalty_strategy in self.penalty_strategies:
            obj_terms.extend(
                penalty_strategy.get_penalty_terms(
                    lp_vars, data_provider, preference_weights
                )
            )

        problem += pulp.lpSum(obj_terms)

        return self.solve_finalize(problem, lp_vars)

    def solve_finalize(
        self,
        problem: pulp.LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
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

        schedule = self._extract_optimized_schedule_from_lp(lp_holder)

        return ScheduleOptimizationResults(True, schedule, constraint_slacks, None)

    @staticmethod
    def _extract_optimized_schedule_from_lp(
        lp_holder: LpNurseShiftVariableHolder,
    ) -> Schedule:
        assignments: dict[str, list[str]] = defaultdict(list)

        # Iterate over the structured Tuple keys
        for (
            employee_id,
            shift_id,
        ), variable in lp_holder.get_all_assignments().items():
            # Check the resolved value
            if (
                variable.varValue and variable.varValue > 0.5
            ):  # 0.5 threshold for floating point safety
                assignments[shift_id].append(employee_id)

        return Schedule(assignments)
