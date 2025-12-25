from dataclasses import dataclass

from snf_schedule_optimizer.models import DomainPrimaryKeyType, EmployeeIdType, Schedule
from snf_schedule_optimizer.models.scheduling.schedule_cost_models import (
    ScheduleFinancialReport,
)
from snf_schedule_optimizer.optimizer.models import ScheduleOptimizationStats
from snf_schedule_optimizer.optimizer.reporting import ScheduleAnalysisReport


@dataclass(frozen=True)
class MoveEmployeeRequest:
    """
    DTO received from the Frontend to validate a drag-and-drop action.
    """

    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    schedule_id: DomainPrimaryKeyType  # DB ID of the current schedule being edited
    schedule_version: int  # For optimistic locking/concurrency check

    employee_id: EmployeeIdType

    # If None, it means the employee was dragged from "Unassigned" pool
    from_shift_id: DomainPrimaryKeyType | None

    # If None, it means employee was dragged to "Unassigned" (removed from shift)
    to_shift_id: DomainPrimaryKeyType | None


@dataclass(frozen=True)
class OptimizationOutput:
    """The complete package returned to the client."""

    is_success: bool
    schedule: Schedule | None
    analysis: ScheduleAnalysisReport | None
    financials: ScheduleFinancialReport | None
    stats: ScheduleOptimizationStats | None
    error_details: str | None = None
