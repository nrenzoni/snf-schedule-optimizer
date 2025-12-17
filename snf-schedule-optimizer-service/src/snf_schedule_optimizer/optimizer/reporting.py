from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import whenever

from snf_schedule_optimizer.models import (
    HprdEnforcedRole,
    NurseProfile,
    PreferenceType,
    Schedule,
    Shift,
    ShiftKey,
)

if TYPE_CHECKING:
    from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider


@dataclass
class ConstraintViolation:
    """Represents a rule that was broken or a target that was missed."""

    category: str  # e.g., "Compliance", "Wellbeing", "Financial"
    rule_name: str
    entity_id: str  # The Shift or Employee involved
    details: str
    severity: str  # "Hard" (Critical) or "Soft" (Penalty incurred)


@dataclass
class ShiftAssignmentDetail:
    """Human-readable detail for a single assignment."""

    shift_id: str
    shift_date: str
    employee_name: str
    employee_role: str
    is_agency: bool
    preference_conflicts: list[str] = field(default_factory=list)


@dataclass
class ScheduleAnalysisReport:
    """The master report containing all extracted insights."""

    assignments: list[ShiftAssignmentDetail]
    violations: list[ConstraintViolation]

    # Summary Metrics
    total_assignments: int
    unfilled_roles: list[str]  # e.g., ["SHIFT_1 (RN)"]
    compliance_score: float  # 0.0 to 100.0 (placeholder for now)


class ScheduleResultAnalyzer:
    """
    Analyzes a raw Schedule object against the Data Provider to extract
    insights, violations, and human-readable summaries.
    """

    def __init__(self, data_provider: IScenarioDataProvider):
        self.provider = data_provider

    def analyze(self, schedule: Schedule) -> ScheduleAnalysisReport:
        assignments_detail = []
        violations = []
        unfilled = []

        # Pre-fetch shifts map for O(1) lookup
        all_shifts = {
            ShiftKey(s.facility_id, s.shift_id): s
            for s in self.provider.get_all_shifts()
        }
        facility_ids = self.provider.get_facility_ids()

        # 1. Analyze Assignments & Preferences (Soft Constraints)
        for key, emp_ids in schedule.shift_assignments.items():
            shift = all_shifts.get(key)
            if shift is None:
                raise ValueError(
                    f"Shift ID {key} in schedule not found in data provider."
                )
            for emp_id in emp_ids:
                emp = self.provider.get_employee_by_id(emp_id)
                # We need the nurse profile for preferences
                # Assuming provider can bridge Employee -> NurseProfile logic
                # (or we iterate nurses_for_shift to find the profile)
                nurses = self.provider.get_nurses_for_shift(shift)
                nurse_profile = next(
                    (n for n in nurses if n.employee_id == emp_id), None
                )

                if not emp or not nurse_profile:
                    continue

                # Check Preferences
                conflicts = self._check_preferences(nurse_profile, shift)
                for conflict in conflicts:
                    violations.append(
                        ConstraintViolation(
                            category="Wellbeing",
                            rule_name="Preference Violation",
                            entity_id=f"{emp.name} on {key.shift_id}",
                            details=conflict,
                            severity="Soft",
                        )
                    )

                # Retrieve Agency Status from Compensation Record
                comp_rec = self.provider.get_compensation_service().get_record_for_date(
                    emp.employee_id, shift.shift_start_dt
                )
                is_agency = comp_rec.is_agency if comp_rec else False

                assignments_detail.append(
                    ShiftAssignmentDetail(
                        shift_id=key.shift_id,
                        shift_date=shift.shift_start_dt.format_iso(),
                        employee_name=emp.name,
                        employee_role=emp.job_title,
                        is_agency=is_agency,
                        preference_conflicts=conflicts,
                    )
                )

        # 2. Analyze Compliance (Hard Constraints - HPRD/Min Staffing)
        for fac_id in facility_ids:
            reqs = self.provider.get_hprd_requirements_for_facility(fac_id)
            shifts = self.provider.get_shifts_for_facility(fac_id)

            for shift in shifts:
                assigned_emp_ids = schedule.shift_assignments.get(
                    shift.shift_key,
                    [],
                )
                assigned_emps = [
                    self.provider.get_employee_by_id(eid) for eid in assigned_emp_ids
                ]
                # Filter out Nones just in case
                valid_emps = [e for e in assigned_emps if e]

                for role in [HprdEnforcedRole.RN, HprdEnforcedRole.CNA]:
                    required_count = reqs[shift.shift_id, role]

                    # Count actuals
                    # Note: Using string comparison for role matching
                    actual_count = sum(
                        1 for e in valid_emps if e.job_title == role.value
                    )

                    # Check for violation (using small epsilon for float safety if needed,
                    # but count is usually integer in this context)
                    if actual_count < int(required_count):
                        miss = int(required_count) - actual_count
                        msg = f"Missing {miss} {role.value}s (Req: {required_count}, Has: {actual_count})"

                        violations.append(
                            ConstraintViolation(
                                category="Compliance",
                                rule_name="Minimum Staffing / HPRD",
                                entity_id=f"{shift.facility_id}_{shift.shift_id}",
                                details=msg,
                                severity="Hard",
                            )
                        )
                        unfilled.append(
                            f"{shift.facility_id}_{shift.shift_id} ({role.value})"
                        )

        return ScheduleAnalysisReport(
            assignments=assignments_detail,
            violations=violations,
            total_assignments=len(assignments_detail),
            unfilled_roles=unfilled,
            compliance_score=100.0,  # Placeholder for scoring logic
        )

    def _check_preferences(self, nurse: NurseProfile, shift: Shift) -> list[str]:
        conflicts: list[str] = []
        if not nurse.shift_custom_preferences:
            return conflicts

        for pref in nurse.shift_custom_preferences:
            # Check Specific Day Off
            if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                # Assuming specific_value is str(day_of_week int)
                if str(shift.day_of_week) == pref.specific_value:
                    conflicts.append(
                        f"Worked on requested day off (Day {shift.day_of_week})"
                    )

            # Check Weekend Off
            elif pref.preference_type == PreferenceType.WEEKEND_OFF:
                if shift.day_of_week in [whenever.SATURDAY, whenever.SUNDAY]:
                    conflicts.append("Worked on weekend preference")

            # Add other preference checks here (Night shift, etc.)

        return conflicts
