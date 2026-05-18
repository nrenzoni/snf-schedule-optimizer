from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from snf_schedule_optimizer.models.main_data_models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
)

if TYPE_CHECKING:
    from snf_schedule_optimizer.models.scheduling.schedule_cost_models import (
        ScheduleFinancialReport,
    )
    from snf_schedule_optimizer.optimizer.models import ScheduleOptimizationStats


@dataclass(frozen=True)
class PreferenceWeights:
    ot_avoidance_penalty: float = 1000.0
    team_consistency_penalty: float = 300.0
    high_risk_shift_penalty: float = 2000.0
    custom_preference_penalty: float = 1500.0
    weekend_fairness_penalty: float = 10.0
    holiday_fairness_penalty: float = 20.0


@dataclass(frozen=True)
class OptimizationSettings:
    use_ml_forecast: bool = False
    use_callout_buffer: bool = True
    buffer_threshold: int = 10
    min_rest_period: int = 10
    max_shift_length: float = 12.0
    premium_weekend: bool = True
    premium_holiday: bool = False
    overtime_avoidance_penalty: float = 1000.0
    team_consistency_penalty: float = 300.0
    high_risk_shift_penalty: float = 2000.0
    custom_preference_penalty: float = 1500.0

    def to_preference_weights(self) -> PreferenceWeights:
        return PreferenceWeights(
            ot_avoidance_penalty=self.overtime_avoidance_penalty,
            team_consistency_penalty=self.team_consistency_penalty,
            high_risk_shift_penalty=self.high_risk_shift_penalty,
            custom_preference_penalty=self.custom_preference_penalty,
        )


@dataclass(frozen=True)
class OptimizationSummary:
    assignments_changed: int
    total_assignments: int
    covered_shifts: int
    uncovered_shifts: int
    completed_at: str
    applied_settings: OptimizationSettings


@dataclass(frozen=True)
class StagedSchedulePatch:
    patch_id: str
    employee_id: EmployeeIdType
    employee_name: str | None = None
    from_shift_id: DomainPrimaryKeyType | None = None
    to_shift_id: DomainPrimaryKeyType | None = None
    pinned: bool = True
    warnings: tuple[str, ...] = ()
    validation_level: str = "ok"
    causes_overtime: bool = False
    total_cost: float = 0.0
    created_at: str | None = None


@dataclass(frozen=True)
class PatchConflict:
    patch_id: str
    employee_id: EmployeeIdType
    employee_name: str | None = None
    from_shift_id: DomainPrimaryKeyType | None = None
    to_shift_id: DomainPrimaryKeyType | None = None
    reason: str = ""
    latest_shift_id: DomainPrimaryKeyType | None = None


@dataclass(frozen=True)
class OptimizationRun:
    """Aggregate Root: consistency boundary is the run lifecycle with atomic status transitions."""

    run_id: str
    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    schedule_id: DomainPrimaryKeyType
    schedule_lineage_id: DomainPrimaryKeyType
    base_schedule_version: int
    result_schedule_id: DomainPrimaryKeyType | None = None
    result_schedule_version: int | None = None
    status: str = "queued"
    stage: str = "queued"
    progress_percent: int = 0
    status_message: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    error_details: str | None = None
    financials: ScheduleFinancialReport | None = None
    stats: ScheduleOptimizationStats | None = None
    summary: OptimizationSummary | None = None
    patches: tuple[StagedSchedulePatch, ...] = ()
    client_request_id: str | None = None
    settings: OptimizationSettings | None = None
    persist_result: bool = True
    decision_start_date: str | None = None
    decision_end_date: str | None = None
    policy_start_date: str | None = None
    policy_end_date: str | None = None
    snapshot_id: str | None = None
    claimed_by: str | None = None
    claim_token: str | None = None
    lease_expires_at: str | None = None
    heartbeat_at: str | None = None
    attempt_count: int = 0
    failure_code: str | None = None
    termination_reason: str | None = None
    cancel_requested_at: str | None = None


@dataclass(frozen=True)
class OptimizationRunEvent:
    run_id: str
    sequence: int
    status: str
    stage: str
    progress_percent: int
    status_message: str = ""
    error_details: str | None = None
    metrics: dict[str, object] | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class OptimizationSnapshot:
    snapshot_id: str
    run_id: str
    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    schedule_id: DomainPrimaryKeyType
    base_schedule_version: int
    decision_start_date: str
    decision_end_date: str
    policy_start_date: str
    policy_end_date: str
    payload: dict[str, object]
    created_at: str | None = None
