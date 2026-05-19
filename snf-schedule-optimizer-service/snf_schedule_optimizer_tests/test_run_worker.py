import asyncio
from typing import cast

import whenever

from snf_schedule_optimizer.api import StartOptimizationRunRequest
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    NurseProfile,
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSettings,
    Schedule,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.persistence.fakes import FakeScheduleRepo, FakeWorkerStore
from snf_schedule_optimizer.service.scheduling.optimization_run_worker import (
    LEASE_SECONDS,
    OptimizationRunWorker,
)
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacade,
)

from .support import OptimizerTestBuilder


def _make_test_run(
    run_id: str,
    claim_token: str = "test-token",
    lease_expires_at: str | None = None,
) -> OptimizationRun:
    return OptimizationRun(
        run_id=run_id,
        org_id=1,
        facility_id=1,
        schedule_id=10,
        schedule_lineage_id=10,
        base_schedule_version=1,
        status="running",
        stage="solving",
        progress_percent=55,
        status_message="Solving",
        client_request_id="test",
        started_at=whenever.Instant.now().format_iso(),
        heartbeat_at=whenever.Instant.now().format_iso(),
        lease_expires_at=lease_expires_at
        or whenever.Instant.now().add(seconds=30).format_iso(),
        claimed_by="test-worker",
        claim_token=claim_token,
        attempt_count=1,
        persist_result=True,
        decision_start_date="2025-01-01",
        decision_end_date="2025-01-07",
        settings=OptimizationSettings(),
    )


def _build_worker_fixture() -> tuple[
    OptimizationRunWorker,
    WorkforceSchedulerFacade,
    FakeScheduleRepo,
    FakeWorkerStore,
]:
    ref_date = whenever.ZonedDateTime(2025, 1, 1, tz="America/New_York")
    employees = [
        Employee(
            employee_id=1,
            name="Test RN",
            job_title="RN",
            hire_date=ref_date.date(),
        ),
        Employee(
            employee_id=2,
            name="Test CNA 1",
            job_title="CNA",
            hire_date=ref_date.date(),
        ),
        Employee(
            employee_id=3,
            name="Test CNA 2",
            job_title="CNA",
            hire_date=ref_date.date(),
        ),
    ]
    nurses = [
        NurseProfile(
            employee_id=employee.employee_id,
            available_hours_weekly=40,
            skills=[employee.job_title],
            shift_custom_preferences=[],
        )
        for employee in employees
    ]
    compensations = [
        StaffCompensationRecord(
            employee_id=employee.employee_id,
            base_rate_effective=30.0,
            ot_multiplier=1.5,
            effective_start_date=ref_date.date(),
            is_agency=False,
        )
        for employee in employees
    ]
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=101),
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date.add(hours=7),
        shift_end_dt=ref_date.add(hours=15),
        unit_id=None,
        is_scheduled=True,
    )
    facility_config = FacilityConfig(
        org_id=1,
        facility_id=1,
        shifts_per_day=3,
        overtime_threshold_hours_per_week=40,
        start_of_work_week_day=whenever.Weekday.MONDAY,
        start_of_work_day_time=whenever.Time(7, 0, 0),
        pay_period=whenever.DateDelta(weeks=1),
        weekend_multiplier=1.0,
        night_shift_multiplier=1.0,
        tz="America/New_York",
        default_hprd_rn=0.0,
        default_hprd_cna=0.0,
        default_hprd_total=0.0,
    )
    schedule = Schedule(
        org_id=1,
        facility_id=1,
        schedule_id=10,
        schedule_lineage_id=10,
        schedule_version=1,
        shift_assignments={shift.shift_key: []},
        start_date="2025-01-01",
        end_date="2025-01-07",
        updated_at=whenever.Instant.now().format_iso(),
    )

    facade = (
        OptimizerTestBuilder()
        .with_employees(employees, nurses)
        .with_financials(compensations)
        .with_shifts([shift])
        .with_facility_configs([facility_config])
        .with_schedule(schedule, schedule_id=10, org_id=1)
        .build_facade()
    )
    schedule_repo = cast(FakeScheduleRepo, facade.schedule_retriever)
    store = FakeWorkerStore(schedule_repo)
    worker = OptimizationRunWorker(
        worker_id="test-worker",
        schedule_repo=schedule_repo,
        scheduler_facade=facade,
        worker_store=store,
    )
    return worker, facade, schedule_repo, store


async def test_worker_executes_queued_run_to_completion() -> None:
    worker, facade, schedule_repo, _store = _build_worker_fixture()

    response = await facade.start_optimization_run(
        StartOptimizationRunRequest(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            base_schedule_version=1,
            start_date="2025-01-01",
            end_date="2025-01-07",
            settings=OptimizationSettings(),
            client_request_id="worker-happy-path",
        )
    )
    assert response.run is not None

    claimed = await worker.run_once()
    assert claimed is True

    run = await schedule_repo.get_optimization_run(response.run.run_id)
    assert run is not None
    assert run.status == "completed"
    assert run.stage == "completed"
    assert run.snapshot_id is not None
    assert run.result_schedule_version == 2

    snapshot = await schedule_repo.get_optimization_snapshot(run.snapshot_id)
    assert snapshot is not None
    events = await schedule_repo.list_optimization_run_events(run.run_id)
    assert [event.sequence for event in events] == [0, 1, 2, 3, 5, 6, 7, 8, 9, 10]
    assert events[-1].status == "completed"


async def test_worker_reclaims_stale_running_run() -> None:
    worker, facade, schedule_repo, _store = _build_worker_fixture()

    response = await facade.start_optimization_run(
        StartOptimizationRunRequest(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            base_schedule_version=1,
            start_date="2025-01-01",
            end_date="2025-01-07",
            settings=OptimizationSettings(),
            client_request_id="stale-run",
        )
    )
    assert response.run is not None

    first_claim = await schedule_repo.claim_next_queued_optimization_run(
        worker_id="dead-worker",
        claim_token="dead-token",
        lease_expires_at=whenever.Instant.now()
        .subtract(seconds=LEASE_SECONDS + 1)
        .format_iso(),
    )
    assert first_claim is not None
    await schedule_repo.commit()

    claimed = await worker.run_once()
    assert claimed is True

    run = await schedule_repo.get_optimization_run(response.run.run_id)
    assert run is not None
    assert run.status == "completed"
    assert run.attempt_count >= 2


async def test_worker_reclaim_skips_duplicate_progress_events() -> None:
    worker, facade, schedule_repo, _store = _build_worker_fixture()

    response = await facade.start_optimization_run(
        StartOptimizationRunRequest(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            base_schedule_version=1,
            start_date="2025-01-01",
            end_date="2025-01-07",
            settings=OptimizationSettings(),
            client_request_id="stale-run-with-event",
        )
    )
    assert response.run is not None

    first_claim = await schedule_repo.claim_next_queued_optimization_run(
        worker_id="dead-worker",
        claim_token="dead-token",
        lease_expires_at=whenever.Instant.now()
        .subtract(seconds=LEASE_SECONDS + 1)
        .format_iso(),
    )
    assert first_claim is not None
    await schedule_repo.append_optimization_run_event(
        OptimizationRunEvent(
            run_id=response.run.run_id,
            sequence=1,
            status="running",
            stage="snapshotting",
            progress_percent=5,
            status_message="Building optimization snapshot",
            created_at=whenever.Instant.now().format_iso(),
        )
    )
    await schedule_repo.commit()

    claimed = await worker.run_once()
    assert claimed is True

    run = await schedule_repo.get_optimization_run(response.run.run_id)
    assert run is not None
    assert run.status == "completed"

    events = await schedule_repo.list_optimization_run_events(run.run_id)
    assert [event.sequence for event in events] == [0, 1, 2, 3, 5, 6, 7, 8, 9, 10]


async def test_worker_emits_failure_event_when_schedule_missing() -> None:
    worker, facade, schedule_repo, _store = _build_worker_fixture()

    response = await facade.start_optimization_run(
        StartOptimizationRunRequest(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            base_schedule_version=1,
            start_date="2025-01-01",
            end_date="2025-01-07",
            settings=OptimizationSettings(),
            client_request_id="missing-schedule",
        )
    )
    assert response.run is not None

    schedule_repo._schedules.clear()

    claimed = await worker.run_once()
    assert claimed is True

    run = await schedule_repo.get_optimization_run(response.run.run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.failure_code == "worker_error"
    assert run.error_details is not None

    events = await schedule_repo.list_optimization_run_events(run.run_id)
    assert events[-1].status == "failed"
    assert events[-1].metrics == {"failure_code": "worker_error"}


async def test_worker_store_fail_persists_failure_event() -> None:
    _, _, schedule_repo, store = _build_worker_fixture()

    run = _make_test_run("test-run-id", claim_token="test-token")
    schedule_repo._runs["test-run-id"] = run

    await store.fail_run(
        run_id="test-run-id",
        claim_token="test-token",
        stage="failed",
        status_message="Simulated failure",
        error_details="Something went wrong",
        failure_code="worker_error",
        final_sequence=99,
    )

    result = await schedule_repo.get_optimization_run("test-run-id")
    assert result is not None
    assert result.status == "failed"
    assert result.stage == "failed"
    assert result.error_details == "Something went wrong"
    assert result.failure_code == "worker_error"
    assert result.claimed_by is None
    assert result.claim_token is None

    events = await schedule_repo.list_optimization_run_events("test-run-id")
    assert events[-1].status == "failed"
    assert events[-1].metrics == {"failure_code": "worker_error"}


async def test_worker_store_claim_returns_none_when_nothing_queued() -> None:
    _, _, _, store = _build_worker_fixture()

    run = await store.claim_next_queued_optimization_run(
        worker_id="test-worker",
        claim_token="token",
        lease_expires_at=whenever.Instant.now().add(seconds=30).format_iso(),
    )
    assert run is None


async def test_worker_store_renew_lease_succeeds_with_matching_token() -> None:
    _, _, schedule_repo, store = _build_worker_fixture()

    run = _make_test_run(
        "renew-test",
        claim_token="valid-token",
        lease_expires_at=whenever.Instant.now().format_iso(),
    )
    schedule_repo._runs["renew-test"] = run

    new_lease = whenever.Instant.now().add(seconds=30).format_iso()
    renewed = await store.renew_optimization_run_lease(
        run_id="renew-test",
        claim_token="valid-token",
        heartbeat_at=whenever.Instant.now().format_iso(),
        lease_expires_at=new_lease,
    )
    assert renewed is True

    updated = schedule_repo._runs["renew-test"]
    assert updated.lease_expires_at == new_lease


async def test_worker_store_renew_lease_fails_with_wrong_token() -> None:
    _, _, schedule_repo, store = _build_worker_fixture()

    run = _make_test_run(
        "renew-test",
        claim_token="valid-token",
        lease_expires_at=whenever.Instant.now().format_iso(),
    )
    schedule_repo._runs["renew-test"] = run

    renewed = await store.renew_optimization_run_lease(
        run_id="renew-test",
        claim_token="wrong-token",
        heartbeat_at=whenever.Instant.now().format_iso(),
        lease_expires_at=whenever.Instant.now().add(seconds=30).format_iso(),
    )
    assert renewed is False


async def test_store_and_repo_operations_do_not_conflict() -> None:
    _, _, schedule_repo, store = _build_worker_fixture()

    run = _make_test_run("concurrent-test", claim_token="concurrent-token")
    schedule_repo._runs[run.run_id] = run

    async def heartbeat() -> None:
        for _ in range(5):
            await store.renew_optimization_run_lease(
                run_id=run.run_id,
                claim_token="concurrent-token",
                heartbeat_at=whenever.Instant.now().format_iso(),
                lease_expires_at=whenever.Instant.now().add(seconds=30).format_iso(),
            )
            await asyncio.sleep(0.001)

    async def progress() -> None:
        for i in range(5):
            progress_run = OptimizationRun(
                **{
                    **run.__dict__,
                    "status": "running",
                    "stage": "solving",
                    "progress_percent": 55 + i,
                    "status_message": f"Progress {i}",
                }
            )
            event = OptimizationRunEvent(
                run_id=run.run_id,
                sequence=100 + i,
                status="running",
                stage="solving",
                progress_percent=55 + i,
                status_message=f"Progress {i}",
                created_at=whenever.Instant.now().format_iso(),
            )
            await store.publish_progress(progress_run, event)
            await asyncio.sleep(0.001)

    await asyncio.gather(heartbeat(), progress())

    final = await schedule_repo.get_optimization_run(run.run_id)
    assert final is not None
    assert final.status == "running"

    events = await schedule_repo.list_optimization_run_events(run.run_id)
    progress_event_count = sum(1 for e in events if e.sequence >= 100)
    assert progress_event_count == 5
