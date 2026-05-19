"""Tests for optimization run retrieval via the facade/API layer."""

import whenever

from snf_schedule_optimizer.api import StartOptimizationRunRequest
from snf_schedule_optimizer.models import OptimizationSettings, Schedule

from ..support import OptimizerTestBuilder


async def test_get_optimization_run_returns_run_after_submission() -> None:
    facade = OptimizerTestBuilder().build_facade()
    schedule_repo = facade.schedule_retriever
    run_repo = facade.optimization_run_repo

    schedule = Schedule(
        org_id=1,
        facility_id=1,
        schedule_id=10,
        schedule_lineage_id=10,
        schedule_version=1,
        shift_assignments={},
        start_date="2025-01-01",
        end_date="2025-01-07",
        updated_at=whenever.Instant.now().format_iso(),
    )
    await schedule_repo.save_schedule(schedule)

    start_response = await facade.start_optimization_run(
        StartOptimizationRunRequest(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            base_schedule_version=1,
            start_date="2025-01-01",
            end_date="2025-01-07",
            settings=OptimizationSettings(),
            client_request_id="get-run-test",
        )
    )
    assert start_response.run is not None

    run = await run_repo.get_optimization_run(start_response.run.run_id)
    assert run is not None
    assert run.status == "queued"
    assert run.stage == "queued"
    assert run.org_id == 1
    assert run.facility_id == 1
    assert run.schedule_id == 10


async def test_get_optimization_run_returns_none_for_unknown_id() -> None:
    facade = OptimizerTestBuilder().build_facade()
    run_repo = facade.optimization_run_repo
    run = await run_repo.get_optimization_run("nonexistent-run-id")
    assert run is None


async def test_get_active_optimization_run_filters_by_org_facility_schedule() -> None:
    facade = OptimizerTestBuilder().build_facade()
    schedule_repo = facade.schedule_retriever
    run_repo = facade.optimization_run_repo

    schedule = Schedule(
        org_id=1,
        facility_id=1,
        schedule_id=10,
        schedule_lineage_id=10,
        schedule_version=1,
        shift_assignments={},
        start_date="2025-01-01",
        end_date="2025-01-07",
        updated_at=whenever.Instant.now().format_iso(),
    )
    await schedule_repo.save_schedule(schedule)

    response = await facade.start_optimization_run(
        StartOptimizationRunRequest(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            base_schedule_version=1,
            start_date="2025-01-01",
            end_date="2025-01-07",
            settings=OptimizationSettings(),
            client_request_id="active-run-filter",
        )
    )
    assert response.run is not None

    active = await run_repo.get_active_optimization_run(
        org_id=1, facility_id=1, schedule_id=10
    )
    assert active is not None
    assert active.run_id == response.run.run_id

    missing = await run_repo.get_active_optimization_run(
        org_id=2, facility_id=1, schedule_id=10
    )
    assert missing is None
