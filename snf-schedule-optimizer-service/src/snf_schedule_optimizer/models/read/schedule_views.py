"""Denormalized read models optimized for schedule display queries."""

from dataclasses import dataclass

import whenever

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
    HprdEnforcedRole,
)


@dataclass(frozen=True)
class ShiftAssignmentView:
    """One row on the schedule board — denormalized for display."""

    shift_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    nurse_id: EmployeeIdType
    nurse_name: str
    role: str
    unit_name: str
    unit_id: DomainPrimaryKeyType | None
    shift_start: whenever.ZonedDateTime
    shift_end: whenever.ZonedDateTime
    is_locked: bool
    cost_cents: int


@dataclass(frozen=True)
class ScheduleDayView:
    """Denormalized view of a single day on the schedule board."""

    date: str  # YYYY-MM-DD
    shifts: list[ShiftAssignmentView]
    hprd_metrics: dict[HprdEnforcedRole, float]
    budget_variance_cents: int
    staffing_gaps: list[str]  # e.g., "Missing RN coverage on unit 101"
    total_staff_count: int
    filled_shift_count: int
    unfilled_shift_count: int
