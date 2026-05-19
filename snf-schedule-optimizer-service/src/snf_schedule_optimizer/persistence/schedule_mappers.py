import json
from typing import Any, cast

from snf_schedule_optimizer.models import (
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSettings,
    OptimizationSummary,
    StagedSchedulePatch,
)
from snf_schedule_optimizer.models.scheduling.schedule_cost_models import (
    CostBreakdown,
    ScheduleFinancialReport,
)
from snf_schedule_optimizer.optimizer.models import ScheduleOptimizationStats
from snf_schedule_optimizer.sqlalchemy_models.optimization_run import (
    OptimizationRunModel,
)
from snf_schedule_optimizer.sqlalchemy_models.optimization_run_event import (
    OptimizationRunEventModel,
)
from snf_schedule_optimizer.utils.serialization import AppJSONEncoder


def incentive_cost(financials: ScheduleFinancialReport | None) -> float | None:
    if financials is None:
        return None
    return sum(
        breakdown.bonuses for breakdown in financials.breakdown_per_facility.values()
    )


def overtime_cost(financials: ScheduleFinancialReport | None) -> float | None:
    if financials is None:
        return None
    return sum(
        breakdown.overtime_cost
        for breakdown in financials.breakdown_per_facility.values()
    )


def regular_cost(financials: ScheduleFinancialReport | None) -> float | None:
    if financials is None:
        return None
    return sum(
        breakdown.regular_cost
        for breakdown in financials.breakdown_per_facility.values()
    )


def patch_to_dict(patch: StagedSchedulePatch) -> dict[str, object]:
    return {
        "patch_id": patch.patch_id,
        "employee_id": patch.employee_id,
        "employee_name": patch.employee_name,
        "from_shift_id": patch.from_shift_id,
        "to_shift_id": patch.to_shift_id,
        "pinned": patch.pinned,
        "warnings": list(patch.warnings),
        "validation_level": patch.validation_level,
        "causes_overtime": patch.causes_overtime,
        "total_cost": patch.total_cost,
        "created_at": patch.created_at,
    }


def patch_from_dict(payload: dict[str, object]) -> StagedSchedulePatch:
    employee_name = payload.get("employee_name")
    from_shift_id = payload.get("from_shift_id")
    to_shift_id = payload.get("to_shift_id")
    warnings = payload.get("warnings")
    created_at = payload.get("created_at")
    return StagedSchedulePatch(
        patch_id=str(payload.get("patch_id", "")),
        employee_id=int(cast(int | str, payload.get("employee_id", 0))),
        employee_name=employee_name if isinstance(employee_name, str) else None,
        from_shift_id=int(from_shift_id)
        if isinstance(from_shift_id, (int, str)) and from_shift_id != ""
        else None,
        to_shift_id=int(to_shift_id)
        if isinstance(to_shift_id, (int, str)) and to_shift_id != ""
        else None,
        pinned=bool(payload.get("pinned", True)),
        warnings=tuple(str(item) for item in warnings)
        if isinstance(warnings, list)
        else (),
        validation_level=str(payload.get("validation_level", "ok")),
        causes_overtime=bool(payload.get("causes_overtime", False)),
        total_cost=float(cast(float | int | str, payload.get("total_cost", 0.0))),
        created_at=created_at if isinstance(created_at, str) else None,
    )


def _settings_to_dict(settings: OptimizationSettings) -> dict[str, object]:
    return {
        "use_ml_forecast": settings.use_ml_forecast,
        "use_callout_buffer": settings.use_callout_buffer,
        "buffer_threshold": settings.buffer_threshold,
        "min_rest_period": settings.min_rest_period,
        "max_shift_length": settings.max_shift_length,
        "premium_weekend": settings.premium_weekend,
        "premium_holiday": settings.premium_holiday,
        "overtime_avoidance_penalty": settings.overtime_avoidance_penalty,
        "team_consistency_penalty": settings.team_consistency_penalty,
        "high_risk_shift_penalty": settings.high_risk_shift_penalty,
        "custom_preference_penalty": settings.custom_preference_penalty,
    }


def dump_settings(settings: OptimizationSettings) -> str:
    return json.dumps(_settings_to_dict(settings), cls=AppJSONEncoder)


def summary_to_dict(
    summary: OptimizationSummary | None,
) -> dict[str, object] | None:
    if summary is None:
        return None
    return {
        "assignments_changed": summary.assignments_changed,
        "total_assignments": summary.total_assignments,
        "covered_shifts": summary.covered_shifts,
        "uncovered_shifts": summary.uncovered_shifts,
        "completed_at": summary.completed_at,
        "applied_settings": _settings_to_dict(summary.applied_settings),
    }


def stats_to_dict(
    stats: ScheduleOptimizationStats | None,
) -> dict[str, object] | None:
    if stats is None:
        return None
    return {
        "execution_time_ms": stats.execution_time_ms,
        "total_variables": stats.total_variables,
        "total_constraints": stats.total_constraints,
        "objective_value": stats.objective_value,
    }


def financials_to_dict(
    financials: ScheduleFinancialReport | None,
) -> dict[str, object] | None:
    if financials is None:
        return None
    return {
        "total_enterprise_cost": financials.total_enterprise_cost,
        "total_incentive_cost": incentive_cost(financials) or 0.0,
        "total_overtime_cost": overtime_cost(financials) or 0.0,
        "regular_pay_cost": regular_cost(financials) or 0.0,
    }


def map_run(model: OptimizationRunModel) -> OptimizationRun:
    stats_payload = (
        cast(dict[str, Any], json.loads(model.stats_json)) if model.stats_json else None
    )
    summary_payload = (
        cast(dict[str, Any], json.loads(model.summary_json))
        if model.summary_json
        else None
    )
    settings_payload = (
        cast(dict[str, Any], json.loads(model.settings_json))
        if model.settings_json
        else None
    )
    financials_payload = (
        cast(dict[str, Any], json.loads(model.financials_json))
        if model.financials_json
        else None
    )
    return OptimizationRun(
        run_id=model.run_id,
        org_id=model.org_id,
        facility_id=model.facility_id,
        schedule_id=model.schedule_id,
        schedule_lineage_id=model.schedule_id,
        base_schedule_version=model.base_schedule_version,
        result_schedule_id=model.result_schedule_id,
        result_schedule_version=model.result_schedule_version,
        status=model.status,
        stage=model.stage,
        progress_percent=model.progress_percent,
        status_message=model.status_message,
        started_at=model.started_at.isoformat(),
        completed_at=model.completed_at.isoformat() if model.completed_at else None,
        error_details=model.error_details,
        financials=ScheduleFinancialReport(
            total_enterprise_cost=float(
                financials_payload.get("total_enterprise_cost", 0.0)
            ),
            breakdown_per_facility={
                model.facility_id: CostBreakdown(
                    regular_cost=float(financials_payload.get("regular_pay_cost", 0.0)),
                    overtime_cost=float(
                        financials_payload.get("total_overtime_cost", 0.0)
                    ),
                    bonuses=float(financials_payload.get("total_incentive_cost", 0.0)),
                )
            },
            breakdown_per_role={},
        )
        if financials_payload
        else None,
        stats=ScheduleOptimizationStats(
            execution_time_ms=float(stats_payload.get("execution_time_ms", 0.0)),
            total_variables=int(stats_payload.get("total_variables", 0)),
            total_constraints=int(stats_payload.get("total_constraints", 0)),
            objective_value=float(stats_payload["objective_value"])
            if stats_payload.get("objective_value") is not None
            else None,
        )
        if stats_payload
        else None,
        summary=OptimizationSummary(
            assignments_changed=int(summary_payload.get("assignments_changed", 0)),
            total_assignments=int(summary_payload.get("total_assignments", 0)),
            covered_shifts=int(summary_payload.get("covered_shifts", 0)),
            uncovered_shifts=int(summary_payload.get("uncovered_shifts", 0)),
            completed_at=str(summary_payload.get("completed_at", "")),
            applied_settings=OptimizationSettings(
                **summary_payload.get("applied_settings", {})
            ),
        )
        if summary_payload
        else None,
        patches=tuple(
            patch_from_dict(payload)
            for payload in json.loads(model.patches_json or "[]")
        ),
        client_request_id=model.client_request_id,
        settings=OptimizationSettings(**settings_payload) if settings_payload else None,
        persist_result=model.persist_result,
        decision_start_date=model.start_date,
        decision_end_date=model.end_date,
        policy_start_date=model.policy_start_date,
        policy_end_date=model.policy_end_date,
        snapshot_id=model.snapshot_id,
        claimed_by=model.claimed_by,
        claim_token=model.claim_token,
        lease_expires_at=model.lease_expires_at.isoformat()
        if model.lease_expires_at
        else None,
        heartbeat_at=model.heartbeat_at.isoformat() if model.heartbeat_at else None,
        attempt_count=model.attempt_count,
        failure_code=model.failure_code,
        termination_reason=model.termination_reason,
        cancel_requested_at=model.cancel_requested_at.isoformat()
        if model.cancel_requested_at
        else None,
    )


def map_run_event(model: OptimizationRunEventModel) -> OptimizationRunEvent:
    return OptimizationRunEvent(
        run_id=model.run_id,
        sequence=model.sequence,
        status=model.status,
        stage=model.stage,
        progress_percent=model.progress_percent,
        status_message=model.status_message,
        error_details=model.error_details,
        metrics=cast(dict[str, object], json.loads(model.metrics_json))
        if model.metrics_json
        else None,
        created_at=model.created_at.isoformat(),
    )
