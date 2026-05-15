from typing import cast

import whenever

from snf_schedule_optimizer.api import StartOptimizationRunRequest
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    NurseProfile,
    OptimizationRunEvent,
    OptimizationSettings,
    Schedule,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.persistence.fakes import FakeScheduleRepo
from snf_schedule_optimizer.service.scheduling.optimization_run_worker import (
    LEASE_SECONDS,
    OptimizationRunWorker,
)
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacade,
)

from .support import OptimizerTestBuilder


def _build_worker_fixture() -> tuple[
    OptimizationRunWorker,
    WorkforceSchedulerFacade,
    FakeScheduleRepo,
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
    worker = OptimizationRunWorker(
        worker_id="test-worker",
        schedule_repo=schedule_repo,
        scheduler_facade=facade,
    )
    return worker, facade, schedule_repo


async def test_worker_executes_queued_run_to_completion() -> None:
    worker, facade, schedule_repo = _build_worker_fixture()

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
    assert [event.sequence for event in events] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert events[-1].status == "completed"


async def test_worker_reclaims_stale_running_run() -> None:
    worker, facade, schedule_repo = _build_worker_fixture()

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
    worker, facade, schedule_repo = _build_worker_fixture()

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
    assert [event.sequence for event in events] == [0, 1, 2, 3, 4, 5, 6, 7]


async def test_worker_emits_failure_event_when_schedule_missing() -> None:
    worker, facade, schedule_repo = _build_worker_fixture()

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
