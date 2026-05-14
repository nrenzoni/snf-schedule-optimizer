from __future__ import annotations

from dataclasses import dataclass

from snf_schedule_optimizer.models import Employee, NurseProfile, Shift


@dataclass(frozen=True)
class CandidateEligibilityResult:
    nurse: NurseProfile
    eligible: bool
    reason: str | None = None


class CandidateEligibilityService:
    def evaluate(
        self,
        nurse: NurseProfile,
        employee: Employee | None,
        shift: Shift,
        already_worked_hours: float,
    ) -> CandidateEligibilityResult:
        if employee is None:
            return CandidateEligibilityResult(nurse, False, "employee_missing")

        if employee.job_title not in {"RN", "LPN", "CNA"}:
            return CandidateEligibilityResult(nurse, False, "non_direct_care_role")

        if nurse.skills is not None and employee.job_title not in nurse.skills:
            return CandidateEligibilityResult(nurse, False, "role_skill_mismatch")

        remaining_hours = nurse.available_hours_weekly - already_worked_hours
        if remaining_hours < shift.duration_hours:
            return CandidateEligibilityResult(nurse, False, "insufficient_weekly_capacity")

        return CandidateEligibilityResult(nurse, True)
