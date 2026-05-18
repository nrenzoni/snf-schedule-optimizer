"""Domain events for cross-context communication."""

from dataclasses import dataclass

from snf_schedule_optimizer.infrastructure.event_bus import DomainEvent
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
    ShiftKey,
)


@dataclass(frozen=True, kw_only=True)
class SchedulePublished(DomainEvent):
    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    schedule_id: DomainPrimaryKeyType | None
    version: int


@dataclass(frozen=True, kw_only=True)
class OptimizationCompleted(DomainEvent):
    run_id: str
    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    status: str
    stage: str
    progress_percent: int


@dataclass(frozen=True, kw_only=True)
class ShiftAssignmentChanged(DomainEvent):
    shift_key: ShiftKey
    org_id: DomainPrimaryKeyType
    previous_nurse_id: EmployeeIdType | None
    new_nurse_id: EmployeeIdType | None
