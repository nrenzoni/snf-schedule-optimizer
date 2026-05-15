from __future__ import annotations

from dataclasses import dataclass

from snf_schedule_optimizer.models import (
    Employee,
    EmployeeStateSnapshot,
    LockedAssignment,
    NurseProfile,
    PTORequest,
    Shift,
)
from snf_schedule_optimizer.optimizer.interfaces import INurseHardBlockChecker


@dataclass(frozen=True)
class CandidateEligibilityResult:
    nurse: NurseProfile
    eligible: bool
    reason: str | None = None


class CandidateEligibilityService:
    def __init__(
        self,
        hard_block_checker: INurseHardBlockChecker | None = None,
    ):
        self._hard_block_checker = hard_block_checker

    def evaluate(
        self,
        nurse: NurseProfile,
        employee: Employee | None,
        shift: Shift,
        already_worked_hours: float,
        employee_state: EmployeeStateSnapshot | None = None,
        locked_assignments_for_emp: list[LockedAssignment] | None = None,
        pto_requests: list[PTORequest] | None = None,
    ) -> CandidateEligibilityResult:
        if employee is None:
            return CandidateEligibilityResult(nurse, False, "employee_missing")

        if pto_requests:
            shift_date = shift.shift_start_dt.date()
            for pto in pto_requests:
                if pto.employee_id == employee.employee_id and pto.date == shift_date:
                    if pto.hours == 0:
                        return CandidateEligibilityResult(nurse, False, "pto_full_day")
                    remaining_available = nurse.available_hours_weekly - already_worked_hours - pto.hours
                    if remaining_available < shift.duration_hours:
                        return CandidateEligibilityResult(nurse, False, "pto_partial_hours")

        if employee.job_title not in {"RN", "LPN", "CNA"}:
            return CandidateEligibilityResult(nurse, False, "non_direct_care_role")

        if nurse.skills is not None and employee.job_title not in nurse.skills:
            return CandidateEligibilityResult(nurse, False, "role_skill_mismatch")

        remaining_hours = nurse.available_hours_weekly - already_worked_hours
        if remaining_hours < shift.duration_hours:
            return CandidateEligibilityResult(nurse, False, "insufficient_weekly_capacity")

        if self._hard_block_checker is not None and self._hard_block_checker.check(nurse, shift):
            return CandidateEligibilityResult(nurse, False, "hard_block")

        if locked_assignments_for_emp:
            for la in locked_assignments_for_emp:
                if la.shift_key == shift.shift_key and la.employee_id == employee.employee_id:
                    return CandidateEligibilityResult(nurse, False, "already_locked_to_shift")

        if employee_state is not None:
            if employee_state.consecutive_days_worked > 0:
                total_potential = employee_state.worked_hours_pay_period + shift.duration_hours
                remaining = nurse.available_hours_weekly - total_potential
                if remaining < 0 and already_worked_hours > 0:
                    return CandidateEligibilityResult(
                        nurse, False, "exceeds_weekly_with_lock_history"
                    )

        return CandidateEligibilityResult(nurse, True)
