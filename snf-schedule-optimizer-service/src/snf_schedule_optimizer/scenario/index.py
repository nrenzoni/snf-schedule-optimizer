from __future__ import annotations

from dataclasses import dataclass, field

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    EmployeeStateSnapshot,
    LockedAssignment,
    NurseProfile,
    Shift,
    ShiftKey,
)


@dataclass(frozen=True)
class ScenarioIndex:
    employees_by_id: dict[DomainPrimaryKeyType, Employee] = field(default_factory=dict)
    shifts_by_key: dict[ShiftKey, Shift] = field(default_factory=dict)
    candidates_by_shift: dict[ShiftKey, tuple[NurseProfile, ...]] = field(
        default_factory=dict
    )
    locked_assignments_by_shift: dict[ShiftKey, tuple[LockedAssignment, ...]] = field(
        default_factory=dict
    )
    employee_state_by_id: dict[DomainPrimaryKeyType, EmployeeStateSnapshot] = field(
        default_factory=dict
    )
