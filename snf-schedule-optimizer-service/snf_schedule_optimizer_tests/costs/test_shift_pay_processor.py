"""I.6: skip_overtime_computation flag prevents OT in straight-time costing."""

from unittest.mock import AsyncMock, MagicMock

import whenever

from snf_schedule_optimizer.domain.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)


async def test_skip_overtime_returns_zero_ot_premium() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=12),
        unit_id=None,
        is_scheduled=True,
    )
    employee = Employee(
        employee_id=1, name="Test", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )
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
    )
    comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    mock_comp_service = MagicMock()
    mock_comp_service.get_record_for_date = AsyncMock(return_value=comp)
    mock_elig = MagicMock()
    mock_elig.get_applicable_rules = AsyncMock(return_value=([], []))

    from snf_schedule_optimizer.domain.payroll.calculations.shift_slicers import (
        TimeOverlapShiftSlicer,
    )

    processor = ShiftPayProcessor(
        eligibility_service=mock_elig,
        slicer=TimeOverlapShiftSlicer(),
        compensation_service=mock_comp_service,
    )

    with_ot = await processor.calculate_detailed_cost(
        employee=employee,
        shift=shift,
        current_weekly_hours=36.0,
        facility_config=config,
        skip_overtime_computation=False,
    )
    assert with_ot.overtime_premium > 0, (
        f"12h shift after 36h = 8h OT expected, got {with_ot.overtime_premium}"
    )

    without_ot = await processor.calculate_detailed_cost(
        employee=employee,
        shift=shift,
        current_weekly_hours=36.0,
        facility_config=config,
        skip_overtime_computation=True,
    )
    assert without_ot.overtime_premium == 0, (
        f"skip_overtime should give 0 premium, got {without_ot.overtime_premium}"
    )
