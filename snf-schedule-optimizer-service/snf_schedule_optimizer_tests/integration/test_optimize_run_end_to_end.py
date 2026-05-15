"""Integration test covering the full optimization run worker pipeline end-to-end."""

from typing import cast

import whenever

from snf_schedule_optimizer.api import StartOptimizationRunRequest
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    NurseProfile,
    OptimizationSettings,
    Schedule,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.persistence.fakes import FakeScheduleRepo
from snf_schedule_optimizer.service.scheduling.optimization_run_worker import (
    OptimizationRunWorker,
)
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacade,
)

from ..support import OptimizerTestBuilder


def _build_e2e_fixture() -> tuple[
    OptimizationRunWorker,
    WorkforceSchedulerFacade,
    FakeScheduleRepo,
]:
    ref_date = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    employees = [
        Employee(1, "RN 1", "RN", ref_date.date()),
        Employee(2, "CNA 1", "CNA", ref_date.date()),
        Employee(3, "CNA 2", "CNA", ref_date.date()),
    ]
    nurses = [NurseProfile(e.employee_id, 40, [e.job_title], []) for e in employees]
    compensations = [
        StaffCompensationRecord(
            employee_id=e.employee_id,
            base_rate_effective=30.0,
            ot_multiplier=1.5,
            is_agency=False,
            effective_start_date=ref_date.date(),
        )
        for e in employees
    ]
    shifts = [
        Shift(
            org_id=1,
            shift_key=ShiftKey(facility_id=1, shift_id=101),
            shift_number=1,
            day_shift=True,
            day_of_week=ref_date.date().day_of_week(),
            shift_start_dt=ref_date,
            shift_end_dt=ref_date.add(hours=8),
            unit_id=None,
            is_scheduled=True,
        ),
        Shift(
            org_id=1,
            shift_key=ShiftKey(facility_id=1, shift_id=102),
            shift_number=2,
            day_shift=True,
            day_of_week=ref_date.date().day_of_week(),
            shift_start_dt=ref_date.add(hours=24),
            shift_end_dt=ref_date.add(hours=32),
            unit_id=None,
            is_scheduled=True,
        ),
    ]
    config = FacilityConfig(
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
        shift_assignments={s.shift_key: [] for s in shifts},
        start_date="2025-01-01",
        end_date="2025-01-07",
        updated_at=whenever.Instant.now().format_iso(),
    )
    facade = (
        OptimizerTestBuilder()
        .with_employees(employees, nurses)
        .with_financials(compensations)
        .with_shifts(shifts)
        .with_facility_configs([config])
        .with_schedule(schedule, schedule_id=10, org_id=1)
        .build_facade()
    )
    schedule_repo = cast(FakeScheduleRepo, facade.schedule_retriever)
    worker = OptimizationRunWorker(
        worker_id="integration-worker",
        schedule_repo=schedule_repo,
        scheduler_facade=facade,
    )
    return worker, facade, schedule_repo


async def test_full_e2e_worker_pipeline() -> None:
    worker, facade, schedule_repo = _build_e2e_fixture()

    response = await facade.start_optimization_run(
        StartOptimizationRunRequest(
            org_id=1,
            facility_id=1,
            schedule_id=10,
            base_schedule_version=1,
            start_date="2025-01-01",
            end_date="2025-01-07",
            settings=OptimizationSettings(),
            client_request_id="e2e-test",
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

    snapshot = await schedule_repo.get_optimization_snapshot(run.snapshot_id)
    assert snapshot is not None
    payload = snapshot.payload
    assert "facility_contexts" in payload
    assert "employees" in payload
    assert "nurses_by_shift" in payload
    assert "compensation" in payload

    events = await schedule_repo.list_optimization_run_events(run.run_id)
    assert len(events) >= 7
    assert events[-1].status == "completed"
