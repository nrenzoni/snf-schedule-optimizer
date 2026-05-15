"""I.5: Overtime risk penalty fires when accumulated hours + shift exceeds capacity."""

import whenever

from snf_schedule_optimizer.domain.scheduling.processors.preference_penalty_processor import (
    PreferencePenaltyProcessorImpl,
)
from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    PreferenceType,
    PreferenceWeights,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
    StaffShiftPreference,
)
from snf_schedule_optimizer.persistence.fakes import FakeStaffCompensationRepo

tz_ny = "America/New_York"


async def test_overtime_risk_penalty_fires_when_near_threshold() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    employee = Employee(
        employee_id=1,
        name="Near OT RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    processor = PreferencePenaltyProcessorImpl(
        staff_compensation_retriever=FakeStaffCompensationRepo([comp]),
    )
    weights = PreferenceWeights(
        custom_preference_penalty=1500.0,
        ot_avoidance_penalty=1000.0,
    )

    penalty_near_ot = await processor.calculate_penalty_cost(
        employee=employee,
        nurse=nurse,
        shift=shift,
        preference_weights=weights,
        accumulated_hours=38.0,
    )
    assert penalty_near_ot > 0, "Should penalize assignment when 38+8 > 40"

    penalty_fresh = await processor.calculate_penalty_cost(
        employee=employee,
        nurse=nurse,
        shift=shift,
        preference_weights=weights,
        accumulated_hours=10.0,
    )
    assert penalty_fresh == 0, "Should not penalize when 10+8 = 18 < 40"


async def test_overtime_risk_not_fired_for_high_capacity_nurse() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    employee = Employee(
        employee_id=2,
        name="High Cap RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=60,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    comp = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    processor = PreferencePenaltyProcessorImpl(
        staff_compensation_retriever=FakeStaffCompensationRepo([comp]),
    )
    weights = PreferenceWeights(
        custom_preference_penalty=1500.0,
        ot_avoidance_penalty=1000.0,
    )

    penalty = await processor.calculate_penalty_cost(
        employee=employee,
        nurse=nurse,
        shift=shift,
        preference_weights=weights,
        accumulated_hours=50.0,
    )
    assert penalty == 0, "50+8=58 < 60 available, no OT risk"


async def test_preference_penalty_and_ot_penalty_accumulate() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=False,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    prefs = [
        StaffShiftPreference(
            preference_type=PreferenceType.DAY_SHIFT_PREFERENCE,
            specific_value=None,
            penalty_weight=7.0,
            is_hard_block=False,
        )
    ]
    employee = Employee(
        employee_id=3,
        name="Pref + OT RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    nurse = NurseProfile(
        employee_id=3,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=prefs,
    )
    comp = StaffCompensationRecord(
        employee_id=3,
        base_rate_effective=25.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    processor = PreferencePenaltyProcessorImpl(
        staff_compensation_retriever=FakeStaffCompensationRepo([comp]),
    )
    weights = PreferenceWeights(
        custom_preference_penalty=1500.0,
        ot_avoidance_penalty=1000.0,
    )

    penalty = await processor.calculate_penalty_cost(
        employee=employee,
        nurse=nurse,
        shift=shift,
        preference_weights=weights,
        accumulated_hours=38.0,
    )

    assert penalty > 1500.0, f"Expected >1500 (1500 pref + OT penalty), got {penalty}"
