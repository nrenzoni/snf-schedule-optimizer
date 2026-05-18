"""Protobuf <-> domain mapping functions for the scheduling RPC handler.

All functions take explicit dependencies (IIdObfuscator, container types)
instead of relying on a handler class.
"""

import logging
from collections import defaultdict
from collections.abc import Mapping
from typing import Any, cast

import whenever
from returns.result import Failure, Result, Success
from that_depends import container_context
from that_depends.providers.context_resources import ContextScopes, SupportsContext

from snf_schedule_optimizer.api import OptimizationOutput
from snf_schedule_optimizer.domain.exceptions import DataIntegrityError
from snf_schedule_optimizer.generated.scheduling.v1 import scheduling_pb2
from snf_schedule_optimizer.infrastructure.composition import ISchedulerContainer
from snf_schedule_optimizer.infrastructure.sqid_converter import (
    DEMO_ID_ALIASES,
    IIdObfuscator,
)
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    OptimizationRun,
    OptimizationSettings,
    OptimizationSummary,
    PatchConflict,
    Schedule,
    Shift,
    ShiftKey,
    StagedSchedulePatch,
)
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacadePort,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status / stage / validation enums
# ---------------------------------------------------------------------------


def map_run_status(status: str) -> str:
    return {
        "queued": "OPTIMIZATION_RUN_STATUS_QUEUED",
        "running": "OPTIMIZATION_RUN_STATUS_RUNNING",
        "completed": "OPTIMIZATION_RUN_STATUS_COMPLETED",
        "failed": "OPTIMIZATION_RUN_STATUS_FAILED",
    }.get(status, "OPTIMIZATION_RUN_STATUS_UNSPECIFIED")


def map_run_stage(stage: str) -> str:
    return {
        "queued": "OPTIMIZATION_RUN_STAGE_QUEUED",
        "rebase": "OPTIMIZATION_RUN_STAGE_SNAPSHOTTING",
        "snapshotting": "OPTIMIZATION_RUN_STAGE_SNAPSHOTTING",
        "indexing": "OPTIMIZATION_RUN_STAGE_INDEXING",
        "building_model": "OPTIMIZATION_RUN_STAGE_BUILDING_MODEL",
        "solving": "OPTIMIZATION_RUN_STAGE_SOLVING",
        "analyzing": "OPTIMIZATION_RUN_STAGE_ANALYZING",
        "persisting": "OPTIMIZATION_RUN_STAGE_PUBLISHING",
        "publishing": "OPTIMIZATION_RUN_STAGE_PUBLISHING",
        "completed": "OPTIMIZATION_RUN_STAGE_COMPLETED",
        "failed": "OPTIMIZATION_RUN_STAGE_FAILED",
    }.get(stage, "OPTIMIZATION_RUN_STAGE_UNSPECIFIED")


def map_validation_level(level: str) -> str:
    return {
        "ok": "VALIDATION_OK",
        "warning": "VALIDATION_WARNING",
        "critical": "VALIDATION_CRITICAL",
        "stale": "VALIDATION_STALE",
        "unspecified": "VALIDATION_LEVEL_UNSPECIFIED",
    }.get(level, "VALIDATION_LEVEL_UNSPECIFIED")


def validation_level_name(level: int) -> str:
    normalized_level = int(level)
    mapping = {
        int(scheduling_pb2.VALIDATION_OK): "ok",
        int(scheduling_pb2.VALIDATION_WARNING): "warning",
        int(scheduling_pb2.VALIDATION_CRITICAL): "critical",
        int(scheduling_pb2.VALIDATION_STALE): "stale",
    }
    return mapping.get(normalized_level, "unspecified")


# ---------------------------------------------------------------------------
# Pure domain <-> protobuf mappings
# ---------------------------------------------------------------------------


def map_financials_from_values(
    financials: Any,
) -> scheduling_pb2.FinancialReport:
    return scheduling_pb2.FinancialReport(
        total_enterprise_cost=financials.total_enterprise_cost,
        total_incentive_cost=sum(
            f.bonuses for f in financials.breakdown_per_facility.values()
        ),
        total_overtime_cost=sum(
            f.overtime_cost for f in financials.breakdown_per_facility.values()
        ),
        regular_pay_cost=sum(
            f.regular_cost for f in financials.breakdown_per_facility.values()
        ),
    )


def map_stats_from_values(stats: Any) -> scheduling_pb2.OptimizationStats:
    return scheduling_pb2.OptimizationStats(
        execution_time_ms=stats.execution_time_ms,
        objective_value=stats.objective_value or 0.0,
        total_variables=stats.total_variables,
        total_constraints=stats.total_constraints,
    )


def map_summary(
    summary: OptimizationSummary,
) -> scheduling_pb2.OptimizationSummary:
    return scheduling_pb2.OptimizationSummary(
        assignments_changed=summary.assignments_changed,
        total_assignments=summary.total_assignments,
        covered_shifts=summary.covered_shifts,
        uncovered_shifts=summary.uncovered_shifts,
        completed_at=summary.completed_at,
        applied_settings=scheduling_pb2.OptimizationSettings(
            use_ml_forecast=summary.applied_settings.use_ml_forecast,
            use_callout_buffer=summary.applied_settings.use_callout_buffer,
            buffer_threshold=summary.applied_settings.buffer_threshold,
            min_rest_period=summary.applied_settings.min_rest_period,
            max_shift_length=summary.applied_settings.max_shift_length,
            premium_weekend=summary.applied_settings.premium_weekend,
            premium_holiday=summary.applied_settings.premium_holiday,
            overtime_avoidance_penalty=(
                summary.applied_settings.overtime_avoidance_penalty
            ),
            team_consistency_penalty=(
                summary.applied_settings.team_consistency_penalty
            ),
            high_risk_shift_penalty=summary.applied_settings.high_risk_shift_penalty,
            custom_preference_penalty=(
                summary.applied_settings.custom_preference_penalty
            ),
        ),
    )


def map_settings(
    settings: scheduling_pb2.OptimizationSettings,
) -> OptimizationSettings:
    return OptimizationSettings(
        use_ml_forecast=settings.use_ml_forecast,
        use_callout_buffer=settings.use_callout_buffer,
        buffer_threshold=settings.buffer_threshold,
        min_rest_period=settings.min_rest_period,
        max_shift_length=settings.max_shift_length,
        premium_weekend=settings.premium_weekend,
        premium_holiday=settings.premium_holiday,
        overtime_avoidance_penalty=settings.overtime_avoidance_penalty,
        team_consistency_penalty=settings.team_consistency_penalty,
        high_risk_shift_penalty=settings.high_risk_shift_penalty,
        custom_preference_penalty=settings.custom_preference_penalty,
    )


# ---------------------------------------------------------------------------
# Compound protobuf mappings (need obfuscator)
# ---------------------------------------------------------------------------


def map_run(
    obfuscator: IIdObfuscator, run: OptimizationRun
) -> scheduling_pb2.OptimizationRun:
    proto_run = scheduling_pb2.OptimizationRun(
        run_id=run.run_id,
        schedule_id=obfuscator.encode(run.schedule_id),
        base_schedule_version=run.base_schedule_version,
        result_schedule_version=run.result_schedule_version or 0,
        status=map_run_status(run.status),
        stage=map_run_stage(run.stage),
        progress_percent=run.progress_percent,
        status_message=run.status_message,
        started_at=run.started_at or "",
        completed_at=run.completed_at or "",
        error_details=run.error_details or "",
    )
    if run.financials is not None:
        proto_run.financials.CopyFrom(map_financials_from_values(run.financials))
    if run.stats is not None:
        proto_run.stats.CopyFrom(map_stats_from_values(run.stats))
    if run.summary is not None:
        proto_run.summary.CopyFrom(map_summary(run.summary))
    return proto_run


def map_patch(
    obfuscator: IIdObfuscator, patch: StagedSchedulePatch
) -> scheduling_pb2.StagedSchedulePatch:
    return scheduling_pb2.StagedSchedulePatch(
        patch_id=patch.patch_id,
        employee_id=obfuscator.encode(patch.employee_id),
        employee_name=patch.employee_name or "",
        from_shift_id=obfuscator.encode(patch.from_shift_id)
        if patch.from_shift_id is not None
        else "",
        to_shift_id=obfuscator.encode(patch.to_shift_id)
        if patch.to_shift_id is not None
        else "",
        pinned=patch.pinned,
        warnings=list(patch.warnings),
        validation_level=map_validation_level(patch.validation_level),
        causes_overtime=patch.causes_overtime,
        total_cost=patch.total_cost,
        created_at=patch.created_at or "",
    )


def map_conflict(
    obfuscator: IIdObfuscator, conflict: PatchConflict
) -> scheduling_pb2.PatchConflict:
    return scheduling_pb2.PatchConflict(
        patch_id=conflict.patch_id,
        employee_id=obfuscator.encode(conflict.employee_id),
        employee_name=conflict.employee_name or "",
        from_shift_id=obfuscator.encode(conflict.from_shift_id)
        if conflict.from_shift_id is not None
        else "",
        to_shift_id=obfuscator.encode(conflict.to_shift_id)
        if conflict.to_shift_id is not None
        else "",
        reason=conflict.reason,
        latest_shift_id=obfuscator.encode(conflict.latest_shift_id)
        if conflict.latest_shift_id is not None
        else "",
    )


# ---------------------------------------------------------------------------
# Business-logic lookups (shift names, unit names, patient census)
# ---------------------------------------------------------------------------


def shift_name(shift_number: int) -> str:
    return {1: "Morning", 2: "Afternoon", 3: "Night"}.get(
        shift_number,
        f"Shift {shift_number}",
    )


def unit_key(unit_id: int | None) -> str:
    return f"unit-{unit_id}" if unit_id is not None else "unit-unknown"


def unit_name(unit_id: int | None) -> str:
    return {
        101: "Short-Term Rehab",
        102: "Long-Term Care",
        103: "Memory Care",
        104: "Skilled/Subacute",
    }.get(unit_id or 0, "Unassigned Unit")


def is_weekend(shift: Shift) -> bool:
    return shift.day_of_week in {whenever.Weekday(6), whenever.Weekday(7)}


def patient_census(shift: Shift) -> int:
    base_by_unit = {101: 34, 102: 48, 103: 32, 104: 24}
    census = base_by_unit.get(shift.unit_id or 0, 36)
    if shift.shift_number == 3:
        census -= 2
    if shift.day_of_week in {whenever.Weekday(1), whenever.Weekday(5)}:
        census += 2
    if is_weekend(shift):
        census -= 1
    return max(census, 18)


def target_hrpd(shift: Shift) -> float:
    target_by_unit = {101: 3.9, 102: 3.55, 103: 3.7, 104: 4.15}
    target = target_by_unit.get(shift.unit_id or 0, 3.65)
    if shift.shift_number == 3:
        target -= 0.25
    if is_weekend(shift):
        target += 0.10
    return round(target, 2)


# ---------------------------------------------------------------------------
# Monthly schedule mapping
# ---------------------------------------------------------------------------


def map_monthly_schedule(
    obfuscator: IIdObfuscator,
    schedule: Schedule,
    shifts: Mapping[ShiftKey, Shift],
    employees: Mapping[int, Employee],
    facility_tz: str,
) -> dict[str, scheduling_pb2.DaySchedule]:
    grouped: dict[str, list[scheduling_pb2.Shift]] = defaultdict(list)
    for shift_key, employee_ids in schedule.shift_assignments.items():
        shift = shifts.get(shift_key)
        if shift is None:
            continue
        shift_date = shift.shift_start_dt.to_tz(facility_tz).date().format_common_iso()
        nurse_messages = []
        for employee_id in employee_ids:
            employee = employees.get(employee_id)
            if employee is None:
                continue
            nurse_messages.append(
                scheduling_pb2.Nurse(
                    id=obfuscator.encode(employee_id),
                    name=employee.name,
                    shift_hours=shift.duration_hours,
                    scheduling_rationale="Seeded demo assignment",
                    role=employee.job_title,
                    is_agency=False,
                )
            )

        actual_hours = sum(nurse.shift_hours for nurse in nurse_messages)
        target = target_hrpd(shift)
        census = patient_census(shift)
        actual_hrpd = actual_hours / census if census else 0.0
        grouped[shift_date].append(
            scheduling_pb2.Shift(
                shift_id=obfuscator.encode(shift.shift_id),
                shift_name=shift_name(shift.shift_number),
                patient_census=census,
                target_hrpd=target,
                actual_hrpd=actual_hrpd,
                is_hrpd_met=actual_hrpd >= target,
                nurses=nurse_messages,
                unit_id=unit_key(shift.unit_id),
                unit_name=unit_name(shift.unit_id),
            )
        )

    return {
        day: scheduling_pb2.DaySchedule(date=day, shifts=day_shifts)
        for day, day_shifts in grouped.items()
    }


# ---------------------------------------------------------------------------
# Patch decode functions (need get_internal_id from handler — lazy import)
# ---------------------------------------------------------------------------


def decode_patch(
    obfuscator: IIdObfuscator,
    patch: scheduling_pb2.StagedSchedulePatch,
) -> Result[StagedSchedulePatch, str]:
    from snf_schedule_optimizer.api.grpc.scheduler_handler import get_internal_id

    employee_id_result = get_internal_id(obfuscator, patch.employee_id, "Employee")
    if isinstance(employee_id_result, Failure):
        return Failure(employee_id_result.failure())
    employee_id = employee_id_result.unwrap()
    if employee_id is None:
        raise DataIntegrityError("Expected non-null value from employee_id decode")
    from_shift_id_result = get_internal_id(
        obfuscator, patch.from_shift_id, "Shift", required=False
    )
    if isinstance(from_shift_id_result, Failure):
        return Failure(from_shift_id_result.failure())
    from_shift_id = from_shift_id_result.unwrap()
    to_shift_id_result = get_internal_id(
        obfuscator, patch.to_shift_id, "Shift", required=False
    )
    if isinstance(to_shift_id_result, Failure):
        return Failure(to_shift_id_result.failure())
    to_shift_id = to_shift_id_result.unwrap()
    return Success(
        StagedSchedulePatch(
            patch_id=patch.patch_id,
            employee_id=employee_id,
            employee_name=patch.employee_name or None,
            from_shift_id=from_shift_id,
            to_shift_id=to_shift_id,
            pinned=patch.pinned,
            warnings=tuple(patch.warnings),
            validation_level=validation_level_name(patch.validation_level),
            causes_overtime=patch.causes_overtime,
            total_cost=patch.total_cost,
            created_at=patch.created_at or None,
        )
    )


def decode_staged_patches(
    obfuscator: IIdObfuscator,
    patches: list[scheduling_pb2.StagedSchedulePatch],
) -> Result[tuple[StagedSchedulePatch, ...], str]:
    decoded: list[StagedSchedulePatch] = []
    for patch in patches:
        result = decode_patch(obfuscator, patch)
        if isinstance(result, Failure):
            return Failure(result.failure())
        decoded.append(result.unwrap())
    return Success(tuple(decoded))


# ---------------------------------------------------------------------------
# Async helpers (need container)
# ---------------------------------------------------------------------------


async def load_schedule_dependencies(
    scheduler_container: type[ISchedulerContainer],
    org_id: int,
    schedule: Schedule,
) -> tuple[Schedule, Mapping[ShiftKey, Shift], Mapping[int, Employee], FacilityConfig]:
    async with container_context(
        cast(SupportsContext[Any], scheduler_container),
        scope=ContextScopes.REQUEST,
    ):
        scheduler_service: WorkforceSchedulerFacadePort = (
            await scheduler_container.scheduler_service.resolve()
        )
        return await scheduler_service.get_monthly_schedule(
            org_id=org_id,
            facility_id=schedule.facility_id,
            start_date=schedule.start_date or "",
        )


async def map_optimize_response(
    id_obfuscator: IIdObfuscator,
    result: OptimizationOutput,
    scheduler_container: type[ISchedulerContainer],
) -> scheduling_pb2.OptimizeScheduleResponse:
    response = scheduling_pb2.OptimizeScheduleResponse(
        is_success=result.is_success,
        error_details=result.error_details or "",
    )
    if result.schedule is None:
        return response
    (
        schedule,
        shifts,
        employees,
        facility_config,
    ) = await load_schedule_dependencies(
        scheduler_container,
        result.schedule.org_id,
        result.schedule,
    )
    for day, day_schedule in map_monthly_schedule(
        obfuscator=id_obfuscator,
        schedule=schedule,
        shifts=shifts,
        employees=employees,
        facility_tz=facility_config.tz,
    ).items():
        response.schedules[day].CopyFrom(day_schedule)
    response.facility_id = DEMO_ID_ALIASES.get(
        facility_config.facility_id,
        id_obfuscator.encode(facility_config.facility_id),
    )
    if result.schedule.schedule_id is None:
        raise ValueError("Optimized schedule is missing schedule_id")
    response.schedule_id = id_obfuscator.encode(result.schedule.schedule_id)
    response.schedule_version = result.schedule.schedule_version
    if result.financials is not None:
        response.financials.CopyFrom(map_financials_from_values(result.financials))
    if result.stats is not None:
        response.stats.CopyFrom(map_stats_from_values(result.stats))
    if result.summary is not None:
        response.summary.CopyFrom(map_summary(result.summary))
    return response


async def map_validation_response(
    id_obfuscator: IIdObfuscator,
    result: OptimizationOutput,
    scheduler_container: type[ISchedulerContainer],
) -> scheduling_pb2.ValidateShiftMoveResponse:
    response = scheduling_pb2.ValidateShiftMoveResponse(
        is_success=result.is_success,
        is_valid=result.is_valid,
        validation_level=map_validation_level(result.validation_level),
        error_details=result.error_details or "",
        total_cost=result.financials.total_enterprise_cost
        if result.financials
        else 0.0,
        latest_schedule_version=result.latest_schedule_version or 0,
        is_stale=result.validation_level == "stale",
    )
    if result.financials is not None:
        response.financials.CopyFrom(map_financials_from_values(result.financials))
    if result.stats is not None:
        response.stats.CopyFrom(map_stats_from_values(result.stats))
    for warning in result.warnings:
        response.warnings.append(warning)
    for conflict in result.conflicts:
        response.conflicts.append(map_conflict(id_obfuscator, conflict))
    if result.patches:
        response.patch.CopyFrom(map_patch(id_obfuscator, result.patches[-1]))
    if result.schedule is not None:
        try:
            (
                schedule,
                shifts,
                employees,
                facility_config,
            ) = await load_schedule_dependencies(
                scheduler_container,
                result.schedule.org_id,
                result.schedule,
            )
            for day, day_schedule in map_monthly_schedule(
                obfuscator=id_obfuscator,
                schedule=schedule,
                shifts=shifts,
                employees=employees,
                facility_tz=facility_config.tz,
            ).items():
                response.affected_schedules[day].CopyFrom(day_schedule)
        except Exception:
            logger.warning(
                "Failed to load schedule dependencies for "
                "validation response org_id=%s",
                result.schedule.org_id,
                exc_info=True,
            )
    return response
