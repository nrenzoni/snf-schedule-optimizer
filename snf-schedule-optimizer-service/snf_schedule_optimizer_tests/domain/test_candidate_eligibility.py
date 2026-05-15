"""Tests for CandidateEligibilityService with hard block checker integration."""


import whenever

from snf_schedule_optimizer.models import (
    Employee,
    LockedAssignment,
    NurseProfile,
    Shift,
    ShiftKey,
    StaffShiftPreference,
)
from snf_schedule_optimizer.models.constraints import PreferenceType
from snf_schedule_optimizer.optimizer.calculators import NurseHardBlockCheckerImpl
from snf_schedule_optimizer.scenario.candidate_eligibility import (
    CandidateEligibilityService,
)


def _make_shift(facility_id: int = 1, shift_id: int = 101, hours: int = 8) -> Shift:
    start = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    return Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id, shift_id),
        shift_number=1,
        day_shift=True,
        day_of_week=start.date().day_of_week(),
        shift_start_dt=start,
        shift_end_dt=start.add(hours=hours),
        unit_id=None,
        is_scheduled=True,
    )


def _make_employee(emp_id: int = 1, job_title: str = "CNA") -> Employee:
    return Employee(
        employee_id=emp_id,
        name=f"Test {job_title}",
        job_title=job_title,
        hire_date=whenever.Date(2024, 1, 1),
    )


def _make_nurse(emp_id: int = 1, skills: list[str] | None = None, weekly_hours: float = 40) -> NurseProfile:
    return NurseProfile(
        employee_id=emp_id,
        available_hours_weekly=weekly_hours,
        skills=skills,
        shift_custom_preferences=[],
    )


def test_eligible_candidate_passes_all_checks() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=_make_nurse(1, ["CNA"]),
        employee=_make_employee(1, "CNA"),
        shift=_make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is True
    assert result.reason is None


def test_missing_employee_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=_make_nurse(1),
        employee=None,
        shift=_make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "employee_missing"


def test_non_direct_care_role_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=_make_nurse(1),
        employee=_make_employee(1, "Manager"),
        shift=_make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "non_direct_care_role"


def test_role_skill_mismatch_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=_make_nurse(1, ["RN"]),
        employee=_make_employee(1, "CNA"),
        shift=_make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "role_skill_mismatch"


def test_insufficient_weekly_capacity_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=_make_nurse(1, ["CNA"], weekly_hours=4),
        employee=_make_employee(1, "CNA"),
        shift=_make_shift(hours=8),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "insufficient_weekly_capacity"


def test_already_locked_to_same_shift_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    shift = _make_shift()
    result = svc.evaluate(
        nurse=_make_nurse(1, ["CNA"]),
        employee=_make_employee(1, "CNA"),
        shift=shift,
        already_worked_hours=0,
        locked_assignments_for_emp=[
            LockedAssignment(employee_id=1, shift_key=shift.shift_key)
        ],
    )
    assert result.eligible is False
    assert result.reason == "already_locked_to_shift"


def test_hard_block_day_off_returns_ineligible_with_checker() -> None:
    svc = CandidateEligibilityService(
        hard_block_checker=NurseHardBlockCheckerImpl()
    )
    shift = _make_shift()
    nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[
            StaffShiftPreference(
                preference_type=PreferenceType.SPECIFIC_DAY_OFF,
                specific_value=str(shift.day_of_week.value),
                penalty_weight=1000,
                is_hard_block=True,
            )
        ],
    )
    result = svc.evaluate(
        nurse=nurse,
        employee=_make_employee(1, "CNA"),
        shift=shift,
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "hard_block"


def test_hard_block_weekend_off_returns_ineligible_with_checker() -> None:
    svc = CandidateEligibilityService(
        hard_block_checker=NurseHardBlockCheckerImpl()
    )
    start = whenever.ZonedDateTime(2025, 1, 4, 7, tz="America/New_York")
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(1, 102),
        shift_number=1,
        day_shift=True,
        day_of_week=start.date().day_of_week(),
        shift_start_dt=start,
        shift_end_dt=start.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[
            StaffShiftPreference(
                preference_type=PreferenceType.WEEKEND_OFF,
                specific_value=None,
                penalty_weight=1000,
                is_hard_block=True,
            )
        ],
    )
    result = svc.evaluate(
        nurse=nurse,
        employee=_make_employee(1, "CNA"),
        shift=shift,
        already_worked_hours=0,
    )
    assert shift.day_of_week in {whenever.Weekday.SATURDAY, whenever.Weekday.SUNDAY}
    assert result.eligible is False
    assert result.reason == "hard_block"
