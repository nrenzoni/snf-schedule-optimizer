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

    assert requirements[101, HprdEnforcedRole.RN] == pytest.approx(1.6)
    assert requirements[101, HprdEnforcedRole.LPN] == pytest.approx(0.8)
    assert requirements[101, HprdEnforcedRole.CNA] == pytest.approx(3.2)
    assert requirements.get_total_req(101) == pytest.approx(4.8)
