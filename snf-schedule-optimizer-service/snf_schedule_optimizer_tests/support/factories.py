"""Shared test factories for domain objects used across test modules."""

from __future__ import annotations

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    NurseProfile,
    Shift,
    ShiftKey,
)


def make_shift(
    facility_id: int = 1,
    shift_id: int = 101,
    hours: int = 8,
    start_hour: int = 7,
    start_day: int = 1,
) -> Shift:
    when = whenever.ZonedDateTime(2025, 1, start_day, start_hour, tz="America/New_York")
    return Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=facility_id, shift_id=shift_id),
        shift_number=1,
        day_shift=start_hour < 18,
        day_of_week=when.date().day_of_week(),
        shift_start_dt=when,
        shift_end_dt=when.add(hours=hours),
        unit_id=None,
        is_scheduled=True,
    )


def make_employee(
    employee_id: int = 1,
    job_title: str = "CNA",
    hire_date: whenever.Date | None = None,
) -> Employee:
    return Employee(
        employee_id=employee_id,
        name=f"Test {job_title}",
        job_title=job_title,
        hire_date=hire_date or whenever.Date(2024, 1, 1),
    )


def make_nurse(
    employee_id: int = 1,
    skills: list[str] | None = None,
    weekly_hours: float = 40,
) -> NurseProfile:
    return NurseProfile(
        employee_id=employee_id,
        available_hours_weekly=weekly_hours,
        skills=skills if skills is not None else ["CNA"],
        shift_custom_preferences=[],
    )


def make_facility_config(
    facility_id: int = 1,
    night_shift_multiplier: float = 1.0,
    weekend_multiplier: float = 1.0,
    max_consecutive_work_days: int | None = None,
) -> FacilityConfig:
    return FacilityConfig(
        org_id=1,
        facility_id=facility_id,
        shifts_per_day=3,
        overtime_threshold_hours_per_week=40,
        start_of_work_week_day=whenever.Weekday.MONDAY,
        start_of_work_day_time=whenever.Time(7, 0, 0),
        pay_period=whenever.DateDelta(weeks=1),
        weekend_multiplier=weekend_multiplier,
        night_shift_multiplier=night_shift_multiplier,
        tz="America/New_York",
        max_consecutive_work_days=max_consecutive_work_days or 5,
    )
