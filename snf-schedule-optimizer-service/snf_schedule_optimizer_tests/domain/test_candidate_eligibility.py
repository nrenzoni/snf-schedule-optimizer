"""Tests for CandidateEligibilityService with hard block checker integration."""

import whenever

from snf_schedule_optimizer.models import (
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

from ..support.factories import make_employee, make_nurse, make_shift


def test_eligible_candidate_passes_all_checks() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=make_nurse(1, ["CNA"]),
        employee=make_employee(1, "CNA"),
        shift=make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is True
    assert result.reason is None


def test_missing_employee_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=make_nurse(1),
        employee=None,
        shift=make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "employee_missing"


def test_non_direct_care_role_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=make_nurse(1),
        employee=make_employee(1, "Manager"),
        shift=make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "non_direct_care_role"


def test_role_skill_mismatch_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=make_nurse(1, ["RN"]),
        employee=make_employee(1, "CNA"),
        shift=make_shift(),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "role_skill_mismatch"


def test_insufficient_weekly_capacity_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    result = svc.evaluate(
        nurse=make_nurse(1, ["CNA"], weekly_hours=4),
        employee=make_employee(1, "CNA"),
        shift=make_shift(hours=8),
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "insufficient_weekly_capacity"


def test_already_locked_to_same_shift_returns_ineligible() -> None:
    svc = CandidateEligibilityService()
    shift = make_shift()
    result = svc.evaluate(
        nurse=make_nurse(1, ["CNA"]),
        employee=make_employee(1, "CNA"),
        shift=shift,
        already_worked_hours=0,
        locked_assignments_for_emp=[
            LockedAssignment(employee_id=1, shift_key=shift.shift_key)
        ],
    )
    assert result.eligible is False
    assert result.reason == "already_locked_to_shift"


def test_hard_block_day_off_returns_ineligible_with_checker() -> None:
    svc = CandidateEligibilityService(hard_block_checker=NurseHardBlockCheckerImpl())
    shift = make_shift()
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
        employee=make_employee(1, "CNA"),
        shift=shift,
        already_worked_hours=0,
    )
    assert result.eligible is False
    assert result.reason == "hard_block"


def test_hard_block_weekend_off_returns_ineligible_with_checker() -> None:
    svc = CandidateEligibilityService(hard_block_checker=NurseHardBlockCheckerImpl())
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
        employee=make_employee(1, "CNA"),
        shift=shift,
        already_worked_hours=0,
    )
    assert shift.day_of_week in {whenever.Weekday.SATURDAY, whenever.Weekday.SUNDAY}
    assert result.eligible is False
    assert result.reason == "hard_block"
