"""I.4: Verify compensation record lookup respects effective date ranges."""

import pytest
import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    ShiftSpecificRequirements,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.calculators import HprdRequirementCalculator
from snf_schedule_optimizer.persistence.fakes import (
    FakeEmployeeRepo,
    FakeMLModelRepo,
    FakeNurseRepo,
    FakeShiftRequirementsRepo,
    FakeStaffCompensationRepo,
    FakeWorkHistoryService,
)
from snf_schedule_optimizer.resident_acuity_repo import FakeResidentAcuityPerShiftRepo

tz_ny = "America/New_York"


def _make_provider(
    comp_service: FakeStaffCompensationRepo,
    employee: Employee,
    nurse: NurseProfile,
) -> ScenarioDataProviderFactory:
    factory = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([employee]),
        nurse_retriever=FakeNurseRepo([nurse]),
        hprd_calculator=HprdRequirementCalculator(
            FakeResidentAcuityPerShiftRepo([]),
            FakeShiftRequirementsRepo(
                default_requirements=ShiftSpecificRequirements(0, 0, 0)
            ),
        ),
        staff_compensation_service=comp_service,
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    )
    return factory


def _make_context() -> FacilityScenarioContext:
    return FacilityScenarioContext(
        facility_id=1,
        shifts=[],
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
        ),
    )


async def test_get_compensation_returns_record_for_exact_date() -> None:
    old_record = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=20.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
        effective_end_date=whenever.Date(2025, 1, 1),
    )
    new_record = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2025, 1, 1),
        effective_end_date=None,
    )
    comp_service = FakeStaffCompensationRepo([old_record, new_record])
    employee = Employee(
        employee_id=1, name="Test RN", job_title="RN", hire_date=whenever.Date(2023, 1, 1)
    )
    nurse = NurseProfile(
        employee_id=1, available_hours_weekly=40, skills=["RN"], shift_custom_preferences=[]
    )
    provider = _make_provider(comp_service, employee, nurse).create(
        org_id=1,
        facility_contexts={1: _make_context()},
        pay_period_start=whenever.ZonedDateTime(2025, 1, 1, tz=tz_ny).to_instant(),
        optimization_start_time=whenever.ZonedDateTime(2025, 1, 2, tz=tz_ny).to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result_old = await provider.get_compensation_for_date(1, whenever.Date(2024, 6, 1))
    assert result_old is not None
    assert result_old.base_rate_effective == pytest.approx(20.0)

    result_new = await provider.get_compensation_for_date(1, whenever.Date(2025, 6, 1))
    assert result_new is not None
    assert result_new.base_rate_effective == pytest.approx(30.0)


async def test_compensation_respects_rate_change_on_boundary() -> None:
    old_rate = StaffCompensationRecord(
        employee_id=5,
        base_rate_effective=25.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 6, 1),
        effective_end_date=whenever.Date(2025, 1, 1),
    )
    new_rate = StaffCompensationRecord(
        employee_id=5,
        base_rate_effective=27.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2025, 1, 1),
        effective_end_date=None,
    )
    comp_service = FakeStaffCompensationRepo([old_rate, new_rate])
    employee = Employee(
        employee_id=5, name="Rate Test", job_title="CNA", hire_date=whenever.Date(2023, 1, 1)
    )
    nurse = NurseProfile(
        employee_id=5, available_hours_weekly=40, skills=["CNA"], shift_custom_preferences=[]
    )
    provider = _make_provider(comp_service, employee, nurse).create(
        org_id=1,
        facility_contexts={1: _make_context()},
        pay_period_start=whenever.ZonedDateTime(2025, 1, 1, tz=tz_ny).to_instant(),
        optimization_start_time=whenever.ZonedDateTime(2025, 1, 2, tz=tz_ny).to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result_pre = await provider.get_compensation_for_date(5, whenever.Date(2024, 12, 30))
    assert result_pre is not None
    assert result_pre.base_rate_effective == pytest.approx(25.0)

    result_post = await provider.get_compensation_for_date(5, whenever.Date(2025, 1, 2))
    assert result_post is not None
    assert result_post.base_rate_effective == pytest.approx(27.0)
