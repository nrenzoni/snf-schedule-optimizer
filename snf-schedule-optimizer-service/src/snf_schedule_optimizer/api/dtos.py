from dataclasses import dataclass
from typing import Any

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
    OptimizationRun,
    OptimizationSettings,
    OptimizationSummary,
    PatchConflict,
    Schedule,
    StagedSchedulePatch,
)
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

    staged_patches: tuple[StagedSchedulePatch, ...] = ()
    patch_id: str | None = None


@dataclass(frozen=True)
class OptimizationSuccess:
    schedule: "Schedule"
    analysis: "ScheduleAnalysisReport | None" = None
    financials: "ScheduleFinancialReport | None" = None
    stats: "ScheduleOptimizationStats | None" = None
    summary: Any | None = None
    warnings: tuple[str, ...] = ()
    validation_level: str = "ok"
    patches: tuple["StagedSchedulePatch", ...] = ()
    conflicts: tuple["PatchConflict", ...] = ()
    latest_schedule_version: int | None = None
    run: Any | None = None
    is_valid: bool = True


@dataclass(frozen=True)
class OptimizationFailure:
    error_details: str
    failure_code: str | None = None
    warnings: tuple[str, ...] = ()
    validation_level: str = "error"


OptimizationOutcome = OptimizationSuccess | OptimizationFailure


@dataclass(frozen=True)
class OptimizationOutput:
    """@deprecated: Use OptimizationOutcome discriminated union instead.

    The complete package returned to the client.
    """

    is_success: bool
    schedule: Schedule | None
    analysis: ScheduleAnalysisReport | None
    financials: ScheduleFinancialReport | None
    stats: ScheduleOptimizationStats | None
    is_valid: bool = True
    summary: OptimizationSummary | None = None
    error_details: str | None = None
    warnings: tuple[str, ...] = ()
    validation_level: str = "ok"
    patches: tuple[StagedSchedulePatch, ...] = ()
    conflicts: tuple[PatchConflict, ...] = ()
    latest_schedule_version: int | None = None
    run: OptimizationRun | None = None

    def to_outcome(self) -> OptimizationOutcome:
        if self.is_success and self.schedule is not None:
            return OptimizationSuccess(
                schedule=self.schedule,
                analysis=self.analysis,
                financials=self.financials,
                stats=self.stats,
                summary=self.summary,
                warnings=self.warnings,
                validation_level=self.validation_level,
                patches=self.patches,
                conflicts=self.conflicts,
                latest_schedule_version=self.latest_schedule_version,
                run=self.run,
                is_valid=self.is_valid,
            )
        return OptimizationFailure(
            error_details=self.error_details or "",
            failure_code=getattr(self, "failure_code", None),
            warnings=self.warnings,
            validation_level=self.validation_level,
        )


@dataclass(frozen=True)
class OptimizeScheduleRequest:
    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    start_date: str
    end_date: str | None
    settings: OptimizationSettings
    persist_result: bool = True


@dataclass(frozen=True)
class StartOptimizationRunRequest:
    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    schedule_id: DomainPrimaryKeyType
    base_schedule_version: int
    start_date: str
    end_date: str | None
    settings: OptimizationSettings
    staged_patches: tuple[StagedSchedulePatch, ...] = ()
    persist_result: bool = True
    client_request_id: str | None = None
    allow_overwrite: bool = False
