import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.persistence.fakes import (
    FakeEmployeeRepo,
    FakeHprdRequirementCalculator,
    FakeMLModelRepo,
    FakeNurseRepo,
    FakeStaffCompensationRepo,
    FakeWorkHistoryService,
)
from snf_schedule_optimizer.reporting.gap_detection import GapDetectionProcessor

tz_ny = "America/New_York"


async def test_uncovered_shift_generates_alert() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 9, 7, tz=tz_ny)
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.THURSDAY,
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=12),
        unit_id=None,
        is_scheduled=True,
    )

    config = FacilityConfig(
        org_id=1, facility_id=1, shifts_per_day=3,
        overtime_threshold_hours_per_week=40,
        start_of_work_week_day=whenever.Weekday.MONDAY,
        start_of_work_day_time=whenever.Time(7, 0, 0),
        pay_period=whenever.DateDelta(weeks=1),
        weekend_multiplier=1.0, night_shift_multiplier=1.0,
        tz=tz_ny,
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([]),
        nurse_retriever=FakeNurseRepo([]),
        hprd_calculator=FakeHprdRequirementCalculator({}),
        staff_compensation_service=FakeStaffCompensationRepo([]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift],
                config=config,
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    processor = GapDetectionProcessor()
    alerts = await processor.detect_gaps(
        shift_assignments={},
        shifts=[shift],
        data_provider=provider,
        facility_contexts={1: FacilityScenarioContext(
            facility_id=1, shifts=[shift], config=config,
        )},
    )

    uncovered = [a for a in alerts if a.gap_type == "UNCOVERED"]
    assert len(uncovered) == 1, f"Expected 1 UNCOVERED alert, got {len(uncovered)}"
    assert uncovered[0].shift_key == shift.shift_key
    assert uncovered[0].severity == "CRITICAL"


async def test_skill_gap_generates_alert() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 9, 7, tz=tz_ny)
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.THURSDAY,
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=12),
        unit_id=None,
        is_scheduled=True,
    )

    config = FacilityConfig(
        org_id=1, facility_id=1, shifts_per_day=3,
        overtime_threshold_hours_per_week=40,
        start_of_work_week_day=whenever.Weekday.MONDAY,
        start_of_work_day_time=whenever.Time(7, 0, 0),
        pay_period=whenever.DateDelta(weeks=1),
        weekend_multiplier=1.0, night_shift_multiplier=1.0,
        tz=tz_ny,
    )

    cna_emp = Employee(
        employee_id=1, name="CNA A", job_title="CNA",
        hire_date=whenever.Date(2024, 1, 1),
    )
    cna_nurse = NurseProfile(
        employee_id=1, available_hours_weekly=40,
        skills=["CNA"], shift_custom_preferences=[],
    )
    cna_comp = StaffCompensationRecord(
        employee_id=1, base_rate_effective=20.0, ot_multiplier=1.5,
        is_agency=False, effective_start_date=whenever.Date(2024, 1, 1),
    )

    fake_hprd = FakeHprdRequirementCalculator(
        {(1, HprdEnforcedRole.RN): 1.0}
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([cna_emp]),
        nurse_retriever=FakeNurseRepo([cna_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([cna_comp]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift],
                config=config,
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    processor = GapDetectionProcessor()
    alerts = await processor.detect_gaps(
        shift_assignments={shift.shift_key: [1]},
        shifts=[shift],
        data_provider=provider,
        facility_contexts={1: FacilityScenarioContext(
            facility_id=1, shifts=[shift], config=config,
        )},
    )

    skill_gaps = [a for a in alerts if a.gap_type == "SKILL_GAP"]
    assert len(skill_gaps) >= 1, (
        f"Expected at least 1 SKILL_GAP alert, got {len(skill_gaps)}"
    )
    rn_gaps = [a for a in skill_gaps if a.role == "RN"]
    assert len(rn_gaps) >= 1, (
        f"Expected SKILL_GAP alert for RN, got {[a.role for a in skill_gaps]}"
    )
