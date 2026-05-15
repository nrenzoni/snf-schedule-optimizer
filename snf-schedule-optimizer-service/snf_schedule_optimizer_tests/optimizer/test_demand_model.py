"""Tests for HPRD demand calculation with unit filtering and ML/callout modifiers."""

import pytest
import whenever

from snf_schedule_optimizer.models import (
    FacilityConfig,
    HprdEnforcedRole,
    MinMandates,
    OptimizationSettings,
    ResidentAcuity,
    Shift,
    ShiftKey,
    ShiftSpecificRequirements,
)
from snf_schedule_optimizer.optimizer.calculators import HprdRequirementCalculator
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.persistence.fakes import FakeShiftRequirementsRepo
from snf_schedule_optimizer.resident_acuity_repo import FakeResidentAcuityPerShiftRepo


async def test_demand_model_filters_census_by_unit_and_uses_modifiers_not_headcount() -> None:
    shift_start = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=101),
        shift_number=1,
        day_shift=True,
        day_of_week=shift_start.date().day_of_week(),
        shift_start_dt=shift_start,
        shift_end_dt=shift_start.add(hours=8),
        unit_id=10,
        is_scheduled=True,
    )
    acuity = [
        ResidentAcuity(
            resident_id=1,
            unit_id=10,
            census_day=shift_start.start_of_day(),
            pt_score_gg=14,
            nta_score=1,
            clinical_category="high",
        ),
        ResidentAcuity(
            resident_id=2,
            unit_id=10,
            census_day=shift_start.start_of_day(),
            pt_score_gg=4,
            nta_score=1,
            clinical_category="base",
        ),
        ResidentAcuity(
            resident_id=3,
            unit_id=20,
            census_day=shift_start.start_of_day(),
            pt_score_gg=14,
            nta_score=8,
            clinical_category="other-unit",
        ),
    ]
    calculator = HprdRequirementCalculator(
        resident_acuity_retriever=FakeResidentAcuityPerShiftRepo(acuity),
        shift_requirements_retriever=FakeShiftRequirementsRepo(
            default_requirements=ShiftSpecificRequirements(
                target_hprd_rn=4.0,
                target_hprd_lpn=2.0,
                target_hprd_cna=8.0,
                target_total_hprd=12.0,
            )
        ),
    )
    context = FacilityScenarioContext(
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
            tz="America/New_York",
        ),
        min_mandates=MinMandates(
            min_rn_hprd=0.0,
            min_lpn_hprd=0.0,
            min_cna_hprd=0.0,
            min_total_hprd=0.0,
            min_staff_per_shift_rn=0,
            min_staff_per_shift_lpn=0,
            min_staff_per_shift_cna=0,
        ),
        optimization_settings=OptimizationSettings(
            use_ml_forecast=True,
            use_callout_buffer=True,
            buffer_threshold=10,
        ),
    )

    requirements = await calculator.calculate_requirements(context)

    assert requirements[101, HprdEnforcedRole.RN] == pytest.approx(1.575 / 3.0, rel=0.01)
    assert requirements[101, HprdEnforcedRole.LPN] == pytest.approx(0.7875 / 3.0, rel=0.01)
    assert requirements[101, HprdEnforcedRole.CNA] == pytest.approx(3.15 / 3.0, rel=0.01)
    assert requirements.get_total_req(101) == pytest.approx(4.725 / 3.0, rel=0.01)


async def test_hprd_scales_with_shift_duration() -> None:
    shift_start = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift_12h = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=102),
        shift_number=1,
        day_shift=True,
        day_of_week=shift_start.date().day_of_week(),
        shift_start_dt=shift_start,
        shift_end_dt=shift_start.add(hours=12),
        unit_id=10,
        is_scheduled=True,
    )
    acuity = [
        ResidentAcuity(
            resident_id=1,
            unit_id=10,
            census_day=shift_start.start_of_day(),
            pt_score_gg=5,
            nta_score=1,
            clinical_category="base",
        ),
    ]
    calculator = HprdRequirementCalculator(
        resident_acuity_retriever=FakeResidentAcuityPerShiftRepo(acuity),
        shift_requirements_retriever=FakeShiftRequirementsRepo(
            default_requirements=ShiftSpecificRequirements(
                target_hprd_rn=3.0,
                target_hprd_lpn=1.0,
                target_hprd_cna=6.0,
                target_total_hprd=10.0,
            )
        ),
    )
    context = FacilityScenarioContext(
        facility_id=1,
        shifts=[shift_12h],
        config=FacilityConfig(
            org_id=1,
            facility_id=1,
            shifts_per_day=2,
            overtime_threshold_hours_per_week=40,
            start_of_work_week_day=whenever.Weekday.MONDAY,
            start_of_work_day_time=whenever.Time(7, 0, 0),
            pay_period=whenever.DateDelta(weeks=1),
            weekend_multiplier=1.0,
            night_shift_multiplier=1.0,
            tz="America/New_York",
        ),
        min_mandates=MinMandates(
            min_rn_hprd=0.0,
            min_lpn_hprd=0.0,
            min_cna_hprd=0.0,
            min_total_hprd=0.0,
            min_staff_per_shift_rn=0,
            min_staff_per_shift_lpn=0,
            min_staff_per_shift_cna=0,
        ),
        optimization_settings=OptimizationSettings(),
    )

    requirements = await calculator.calculate_requirements(context)
    expected = 3.0 * 1 * (12.0 / 24.0) * 1.05 / 12.0
    assert requirements[102, HprdEnforcedRole.RN] == pytest.approx(expected, rel=0.01)
    assert requirements[102, HprdEnforcedRole.CNA] == pytest.approx(
        6.0 * 1 * (12.0 / 24.0) * 1.05 / 12.0, rel=0.01
    )


async def test_hprd_headcount_independent_of_shift_duration() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    acuity = [
        ResidentAcuity(1, 10, ref.start_of_day(), 5, 1, "base"),
    ]
    calculator = HprdRequirementCalculator(
        resident_acuity_retriever=FakeResidentAcuityPerShiftRepo(acuity),
        shift_requirements_retriever=FakeShiftRequirementsRepo(
            default_requirements=ShiftSpecificRequirements(3.0, 1.0, 6.0, 10.0)
        ),
    )

    def make_ctx(hours: int) -> FacilityScenarioContext:
        shift = Shift(
            org_id=1, shift_key=ShiftKey(facility_id=1, shift_id=300 + hours),
            shift_number=1, day_shift=True,
            day_of_week=ref.date().day_of_week(),
            shift_start_dt=ref,
            shift_end_dt=ref.add(hours=hours),
            unit_id=10, is_scheduled=True,
        )
        return FacilityScenarioContext(
            facility_id=1, shifts=[shift],
            config=FacilityConfig(
                org_id=1, facility_id=1, shifts_per_day=24 // hours,
                overtime_threshold_hours_per_week=40,
                start_of_work_week_day=whenever.Weekday.MONDAY,
                start_of_work_day_time=whenever.Time(7, 0, 0),
                pay_period=whenever.DateDelta(weeks=1),
                weekend_multiplier=1.0, night_shift_multiplier=1.0, tz="America/New_York",
            ),
            min_mandates=MinMandates(0.0, 0.0, 0.0, 0.0, 0, 0, 0),
            optimization_settings=OptimizationSettings(
                use_ml_forecast=False, use_callout_buffer=False
            ),
        )

    req_8 = await calculator.calculate_requirements(make_ctx(8))
    req_12 = await calculator.calculate_requirements(make_ctx(12))

    rn_8 = req_8[308, HprdEnforcedRole.RN]
    rn_12 = req_12[312, HprdEnforcedRole.RN]

    assert rn_8 == pytest.approx(3.0 * 1 / 24.0, rel=0.01), (
        f"8h shift RN headcount: expected {3.0/24.0:.4f}, got {rn_8:.4f}"
    )
    assert rn_12 == pytest.approx(3.0 * 1 / 24.0, rel=0.01), (
        f"12h shift RN headcount: expected {3.0/24.0:.4f}, got {rn_12:.4f}"
    )
