import whenever

from snf_schedule_optimizer.api import StartOptimizationRunRequest
from snf_schedule_optimizer.domain.scheduling.interfaces import ScheduleLookupKey
from snf_schedule_optimizer.models import OptimizationSettings, Schedule

from .test_builder import OptimizerTestBuilder


async def test_duplicate_client_request_id_returns_same_active_run() -> None:
    facade = OptimizerTestBuilder().build_facade()
    schedule_repo = facade.schedule_retriever

    schedule = Schedule(
        org_id=1,
        facility_id=1,
        schedule_id=10,
        schedule_lineage_id=10,
        schedule_version=3,
        shift_assignments={},
        start_date="2025-01-01",
        end_date="2025-01-07",
        updated_at=whenever.Instant.now().format_iso(),
    )
    await schedule_repo.save_schedule(schedule)

    request = StartOptimizationRunRequest(
        org_id=1,
        facility_id=1,
        schedule_id=10,
        base_schedule_version=3,
        start_date="2025-01-01",
        end_date="2025-01-07",
        settings=OptimizationSettings(),
        client_request_id="dedupe-me",
    )

    first = await facade.start_optimization_run(request)
    second = await facade.start_optimization_run(request)

    assert first.is_success
    assert first.run is not None
    assert second.is_success
    assert second.run is not None
    assert second.run.run_id == first.run.run_id

    events = await schedule_repo.list_optimization_run_events(first.run.run_id)
    assert len(events) == 1
    assert events[0].sequence == 0
    assert events[0].status == "queued"
    assert events[0].stage == "queued"

    active_run = await schedule_repo.get_active_optimization_run(
        org_id=1,
        facility_id=1,
        schedule_id=10,
    )
    assert active_run is not None
    assert active_run.run_id == first.run.run_id
    assert await schedule_repo.get_schedule(ScheduleLookupKey(1, 10)) is not None
