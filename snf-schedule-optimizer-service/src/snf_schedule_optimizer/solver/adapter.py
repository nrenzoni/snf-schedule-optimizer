from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from typing import Protocol

import pulp

from snf_schedule_optimizer.infrastructure.circuit_breaker import CircuitBreaker
from snf_schedule_optimizer.models import SolverTerminationReason


@dataclass(frozen=True)
class SolverResult:
    termination_reason: SolverTerminationReason
    status_code: int
    status_label: str
    objective_value: float | None
    elapsed_ms: float


class SolverAdapter(Protocol):
    def solve(self, problem: pulp.LpProblem) -> SolverResult:
        """Solve an LP problem and return structured termination metadata."""


class CbcSolverAdapter:
    def __init__(self, time_limit_seconds: int = 60) -> None:
        self.time_limit_seconds = time_limit_seconds
        self._breaker = CircuitBreaker(failure_threshold=3, reset_timeout=120.0)

    def solve(self, problem: pulp.LpProblem) -> SolverResult:
        return self._breaker.call_sync(self._actual_solve, problem)

    def _actual_solve(self, problem: pulp.LpProblem) -> SolverResult:
        solver = self._build_solver()
        start_time = time.perf_counter()
        problem.solve(solver)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        status_label = pulp.LpStatus[problem.status]
        return SolverResult(
            termination_reason=self._termination_reason(problem.status, status_label),
            status_code=problem.status,
            status_label=status_label,
            objective_value=pulp.value(problem.objective)
            if problem.status == pulp.LpStatusOptimal
            else None,
            elapsed_ms=elapsed_ms,
        )

    def _build_solver(self) -> pulp.LpSolver:
        cbc_path = os.getenv("CBC_PATH")
        if cbc_path:
            return pulp.COIN_CMD(timeLimit=self.time_limit_seconds, path=cbc_path)

        detected_cbc = shutil.which("cbc")
        if detected_cbc:
            return pulp.COIN_CMD(timeLimit=self.time_limit_seconds, path=detected_cbc)

        return pulp.PULP_CBC_CMD(timeLimit=self.time_limit_seconds)

    @staticmethod
    def _termination_reason(
        status_code: int,
        status_label: str,
    ) -> SolverTerminationReason:
        if status_code == pulp.LpStatusOptimal:
            return SolverTerminationReason.OPTIMAL
        if status_code == pulp.LpStatusInfeasible:
            return SolverTerminationReason.INFEASIBLE
        if status_label.lower() in {"not solved", "undefined"}:
            return SolverTerminationReason.TIMEOUT
        return SolverTerminationReason.INTERNAL_ERROR
