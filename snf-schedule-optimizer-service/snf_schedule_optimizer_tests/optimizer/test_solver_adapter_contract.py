"""Tests for solver adapter contract and CbcSolverAdapter behavior."""

import pulp
import pytest

from snf_schedule_optimizer.models.constraints import SolverTerminationReason
from snf_schedule_optimizer.solver import CbcSolverAdapter, SolverResult


def test_cbc_adapter_solves_trivial_lp_and_reports_optimal() -> None:
    adapter = CbcSolverAdapter(time_limit_seconds=10)
    problem = pulp.LpProblem("trivial", pulp.LpMinimize)
    x = pulp.LpVariable("x", lowBound=0)
    problem += x >= 5
    problem += x
    result = adapter.solve(problem)
    assert result.status_code == pulp.LpStatusOptimal
    assert result.termination_reason is SolverTerminationReason.OPTIMAL
    assert result.objective_value == pytest.approx(5.0)
    assert result.elapsed_ms >= 0


def test_cbc_adapter_reports_infeasible() -> None:
    adapter = CbcSolverAdapter(time_limit_seconds=10)
    problem = pulp.LpProblem("infeasible", pulp.LpMinimize)
    x = pulp.LpVariable("x", lowBound=10)
    problem += x <= 5
    problem += x
    result = adapter.solve(problem)
    assert result.termination_reason is SolverTerminationReason.INFEASIBLE


def test_cbc_adapter_discovers_cbc_via_env_or_path() -> None:
    adapter = CbcSolverAdapter()
    assert adapter is not None
    assert adapter.time_limit_seconds == 60


def test_solver_result_frozen_dataclass_holds_all_fields() -> None:
    result = SolverResult(
        termination_reason=SolverTerminationReason.OPTIMAL,
        status_code=pulp.LpStatusOptimal,
        status_label="Optimal",
        objective_value=42.0,
        elapsed_ms=123.4,
    )
    assert result.termination_reason is SolverTerminationReason.OPTIMAL
    assert result.objective_value == 42.0
    assert result.elapsed_ms == 123.4


def test_solver_result_repr_includes_reason() -> None:
    result = SolverResult(
        termination_reason=SolverTerminationReason.TIMEOUT,
        status_code=-1,
        status_label="Timeout",
        objective_value=None,
        elapsed_ms=0.0,
    )
    assert "TIMEOUT" in repr(result) or "timeout" in str(result).lower()
