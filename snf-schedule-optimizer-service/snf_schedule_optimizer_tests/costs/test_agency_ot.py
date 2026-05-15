"""I.3: Agency nurses accrue OT at the standard multiplier, not 1.0."""

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    PreferenceWeights,
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
from snf_schedule_optimizer_tests.support import OptimizerTestBuilder

tz_ny = "America/New_York"


async def test_agency_nurse_ot_multiplier_equals_staff() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 6, tz=tz_ny)

    agency_emp = Employee(
        employee_id=1,
        name="Agency RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    staff_emp = Employee(
        employee_id=2,
        name="Staff RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    agency_comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=50.0,
        ot_multiplier=1.5,
        is_agency=True,
        effective_start_date=whenever.Date(2024, 1, 1),
    )
    staff_comp = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=50.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )
    agency_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=60,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    staff_nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=60,
        skills=["RN"],
        shift_custom_preferences=[],
    )

    employees = [agency_emp, staff_emp]
    nurses = [agency_nurse, staff_nurse]
    comps = [agency_comp, staff_comp]

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={(10, HprdEnforcedRole.RN): 2.0}
    )
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=10),
        shift_number=1,
        day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    optimizer = (
        OptimizerTestBuilder()
        .with_employees(employees, nurses)
        .with_financials(comps)
        .with_hprd_calculator(fake_hprd)
        .build_optimizer()
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo(employees),
        nurse_retriever=FakeNurseRepo(nurses),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo(comps),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift],
                config=FacilityConfig(
                    org_id=1,
                    facility_id=1,
                    shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0,
                    night_shift_multiplier=1.0,
                    tz=tz_ny,
                    agency_ot_multiplier=1.5,
                ),
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments
    shift_staff = assignments.get(ShiftKey(1, 10), [])
    assert len(shift_staff) == 2
    assert 1 in shift_staff, "Agency nurse should be assigned"
    assert 2 in shift_staff, "Staff nurse should be assigned"
