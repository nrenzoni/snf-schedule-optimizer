from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

from snf_schedule_optimizer.models.main_data_models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
)
from snf_schedule_optimizer.models.scheduling.shift import ShiftKey

if TYPE_CHECKING:
    from snf_schedule_optimizer.models.scheduling.optimization import (
        OptimizationSummary,
    )
    from snf_schedule_optimizer.models.scheduling.schedule_cost_models import (
        ScheduleFinancialReport,
    )
    from snf_schedule_optimizer.optimizer.models import ScheduleOptimizationStats


type ShiftAssignmentsType = dict[ShiftKey, list[EmployeeIdType]]


@dataclass(frozen=True)
class Schedule:
    """
    Represents the final output of the scheduling process.

    Aggregate Root: consistency boundary is the schedule with optimistic locking via schedule_version.
    """

    org_id: DomainPrimaryKeyType

    facility_id: DomainPrimaryKeyType | None = None
    schedule_id: DomainPrimaryKeyType | None = None
    schedule_lineage_id: DomainPrimaryKeyType | None = None
    schedule_version: int = 1

    shift_assignments: ShiftAssignmentsType = dataclasses.field(
        default_factory=dict
    )
    start_date: str | None = None
    end_date: str | None = None
    latest_optimization: OptimizationSummary | None = None
    latest_optimization_stats: ScheduleOptimizationStats | None = None
    latest_optimization_financials: ScheduleFinancialReport | None = None
    updated_at: str | None = None

    def get_assigned_employees(self, facility_id: int, shift_id: int) -> list[int]:
        key = ShiftKey(facility_id, shift_id)
        return self.shift_assignments.get(key, [])


@dataclass(frozen=True)
class LockedAssignment:
    employee_id: EmployeeIdType
    shift_key: ShiftKey
    created_at: str | None = None
    source: str = "snapshot"
