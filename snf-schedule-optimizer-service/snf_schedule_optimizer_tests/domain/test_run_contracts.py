"""Tests for optimization run contract enum serialization values."""

from snf_schedule_optimizer.models.constraints import (
    OptimizationFailureCode,
    OptimizationRunStage,
    OptimizationRunStatus,
    SolverTerminationReason,
)


def test_run_contract_enums_serialize_to_expected_values() -> None:
    assert OptimizationRunStatus.QUEUED.value == "queued"
    assert OptimizationRunStage.SOLVING.value == "solving"
    assert OptimizationFailureCode.SOLVER_TIMEOUT.value == "solver_timeout"
    assert SolverTerminationReason.OPTIMAL.value == "optimal"
