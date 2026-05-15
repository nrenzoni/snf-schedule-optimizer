from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

import whenever

from snf_schedule_optimizer.api import StartOptimizationRunRequest
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IScheduleRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    LockedAssignment,
    MinMandates,
    OptimizationFailureCode,
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationRunStage,
    OptimizationRunStatus,
    OptimizationSettings,
    OptimizationSnapshot,
    PatchConflict,
    Schedule,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.optimizer.snapshot_provider import (
    SnapshotScenarioDataProvider,
)
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacade,
)

LEASE_SECONDS = 30
POLL_SECONDS = 1.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerClaim:
    run: OptimizationRun
    claim_token: str


class OptimizationRunWorker:
    def __init__(
        self,
        worker_id: str,
        schedule_repo: IScheduleRepo,
        scheduler_facade: WorkforceSchedulerFacade,
    ) -> None:
        self.worker_id = worker_id
        self.schedule_repo = schedule_repo
        self.scheduler_facade = scheduler_facade

    async def run_forever(self, stop_event: asyncio.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            claimed = await self._claim_once()
            if claimed is None:
                await asyncio.sleep(POLL_SECONDS)
                continue
            await self._execute_claimed_run(claimed)

    async def run_once(self) -> bool:
        claimed = await self._claim_once()
        if claimed is None:
            return False
        await self._execute_claimed_run(claimed)
        return True

    async def _claim_once(self) -> WorkerClaim | None:
        claim_token = uuid4().hex
        lease_expires_at = (
            whenever.Instant.now().add(seconds=LEASE_SECONDS).format_iso()
        )
        run = await self.schedule_repo.claim_next_queued_optimization_run(
            worker_id=self.worker_id,
            claim_token=claim_token,
            lease_expires_at=lease_expires_at,
        )
        if run is None:
            return None
        await self.schedule_repo.commit()
        return WorkerClaim(run=run, claim_token=claim_token)

    async def _execute_claimed_run(self, claim: WorkerClaim) -> None:
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(claim))
        current_run = claim.run
        try:
            current_run = await self._publish_progress(
                current_run,
                sequence=1,
                status=OptimizationRunStatus.RUNNING.value,
                stage=OptimizationRunStage.SNAPSHOTTING.value,
                progress_percent=5,
                status_message="Building optimization snapshot",
                claim_token=claim.claim_token,
            )

            request = self._request_from_run(current_run)
            base_schedule = await self.schedule_repo.get_schedule(
                ScheduleLookupKey(current_run.org_id, current_run.schedule_id),
                include_latest_run=False,
            )
            if base_schedule is None:
                raise ValueError("Base schedule not found for claimed run.")

            facility_context = await self.scheduler_facade._build_optimization_context(
                org_id=request.org_id,
                facility_id=request.facility_id,
                start_date=request.start_date,
                end_date=request.end_date or request.start_date,
                optimization_settings=request.settings,
            )

            facility_contexts = {request.facility_id: facility_context}
            pay_period_start = (
                facility_context.shifts[0].shift_start_dt.start_of_day().to_instant()
            )

            live_provider = self.scheduler_facade.create_data_provider(
                org_id=request.org_id,
                facility_contexts=facility_contexts,
                pay_period_start=pay_period_start,
                optimization_start_time=whenever.Instant.now(),
                optimization_settings=request.settings,
            )

            snapshot = await self._build_snapshot(
                current_run, request, base_schedule, facility_context, live_provider
            )
            await self.schedule_repo.save_optimization_snapshot(snapshot)
            current_run = replace(
                current_run,
                snapshot_id=snapshot.snapshot_id,
                policy_start_date=snapshot.policy_start_date,
                policy_end_date=snapshot.policy_end_date,
            )
            await self.schedule_repo.save_optimization_run(current_run)
            await self.schedule_repo.commit()

            snapshot_data_provider = SnapshotScenarioDataProvider.from_snapshot_payload(
                snapshot.payload
            )

            current_run = await self._publish_progress(
                current_run,
                sequence=2,
                status=OptimizationRunStatus.RUNNING.value,
                stage=OptimizationRunStage.INDEXING.value,
                progress_percent=15,
                status_message="Indexing scenario data from snapshot",
                claim_token=claim.claim_token,
                metrics={"snapshot_id": snapshot.snapshot_id},
            )

            current_run = await self._publish_progress(
                current_run,
                sequence=3,
                status=OptimizationRunStatus.RUNNING.value,
                stage=OptimizationRunStage.BUILDING_MODEL.value,
                progress_percent=30,
                status_message="Building optimization model",
                claim_token=claim.claim_token,
            )

            current_run = await self._publish_progress(
                current_run,
                sequence=4,
                status=OptimizationRunStatus.RUNNING.value,
                stage=OptimizationRunStage.SOLVING.value,
                progress_percent=55,
                status_message="Solving staffing plan",
                claim_token=claim.claim_token,
            )

            locked_assignments = self._locked_assignments_from_snapshot(snapshot)
            result = await self.scheduler_facade.optimize_schedule(
                org_id=request.org_id,
                facility_contexts=facility_contexts,
                preference_weights=request.settings.to_preference_weights(),
                pay_period_start=pay_period_start,
                optimization_settings=request.settings,
                locked_assignments=locked_assignments,
                data_provider=snapshot_data_provider,
            )

            if not result.is_success or result.schedule is None:
                await self._finish_failure(
                    claim,
                    stage="failed",
                    status_message="Optimization failed",
                    error_details=result.error_details,
                    failure_code=OptimizationFailureCode.SOLVER_INFEASIBLE.value,
                    final_sequence=5,
                )
                return

            current_run = await self._publish_progress(
                current_run,
                sequence=5,
                status=OptimizationRunStatus.RUNNING.value,
                stage=OptimizationRunStage.ANALYZING.value,
                progress_percent=80,
                status_message="Analyzing staffing plan",
                claim_token=claim.claim_token,
            )

            latest_version = await self.schedule_repo.get_latest_schedule_version(
                request.org_id,
                request.schedule_id,
            )
            next_version = (latest_version or 0) + 1

            persisted_schedule = self.scheduler_facade._build_persisted_schedule(
                org_id=request.org_id,
                facility_id=request.facility_id,
                schedule_id=request.schedule_id,
                version=next_version,
                assignments=result.schedule.shift_assignments,
                start_date=request.start_date,
                end_date=request.end_date,
                summary=result.summary,
                stats=result.stats,
                financials=result.financials,
            )

            current_run = await self._publish_progress(
                current_run,
                sequence=6,
                status=OptimizationRunStatus.RUNNING.value,
                stage=OptimizationRunStage.PUBLISHING.value,
                progress_percent=92,
                status_message="Publishing optimized schedule",
                claim_token=claim.claim_token,
            )

            if request.persist_result:
                await self.schedule_repo.save_schedule(persisted_schedule)

            final_run = replace(
                current_run,
                status=OptimizationRunStatus.COMPLETED.value,
                stage=OptimizationRunStage.COMPLETED.value,
                progress_percent=100,
                status_message="Optimization completed",
                completed_at=whenever.Instant.now().format_iso(),
                result_schedule_id=(
                    persisted_schedule.schedule_id if request.persist_result else None
                ),
                result_schedule_version=(
                    persisted_schedule.schedule_version
                    if request.persist_result
                    else None
                ),
                financials=result.financials,
                stats=result.stats,
                summary=result.summary,
                snapshot_id=snapshot.snapshot_id,
            )
            await self.schedule_repo.save_optimization_run(final_run)
            await self.schedule_repo.append_optimization_run_event(
                OptimizationRunEvent(
                    run_id=claim.run.run_id,
                    sequence=7,
                    status=OptimizationRunStatus.COMPLETED.value,
                    stage=OptimizationRunStage.COMPLETED.value,
                    progress_percent=100,
                    status_message="Optimization completed",
                    metrics={
                        "result_schedule_version": persisted_schedule.schedule_version
                        if request.persist_result
                        else None
                    },
                    created_at=whenever.Instant.now().format_iso(),
                )
            )
            await self.schedule_repo.release_optimization_run_claim(
                run_id=claim.run.run_id,
                claim_token=claim.claim_token,
                status=OptimizationRunStatus.COMPLETED.value,
                stage=OptimizationRunStage.COMPLETED.value,
                status_message="Optimization completed",
            )
            await self.schedule_repo.commit()
        except Exception as exc:
            await self.schedule_repo.rollback()
            try:
                await self._finish_failure(
                    claim,
                    stage=OptimizationRunStage.FAILED.value,
                    status_message="Optimization worker failed",
                    error_details=str(exc),
                    failure_code=OptimizationFailureCode.WORKER_ERROR.value,
                    final_sequence=99,
                )
            except Exception:
                await self.schedule_repo.rollback()
                logger.exception(
                    "failed to persist optimization run failure run_id=%s",
                    claim.run.run_id,
                )
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

    async def _heartbeat_loop(self, claim: WorkerClaim) -> None:
        while True:
            await asyncio.sleep(LEASE_SECONDS / 3)
            now = whenever.Instant.now().format_iso()
            lease = whenever.Instant.now().add(seconds=LEASE_SECONDS).format_iso()
            renewed = await self._renew_lease(
                claim.run.run_id, claim.claim_token, now, lease
            )
            if not renewed:
                return

    async def _renew_lease(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool:
        renewed = await self.schedule_repo.renew_optimization_run_lease(
            run_id=run_id,
            claim_token=claim_token,
            heartbeat_at=heartbeat_at,
            lease_expires_at=lease_expires_at,
        )
        if renewed:
            await self.schedule_repo.commit()
        return renewed

    async def _publish_progress(
        self,
        run: OptimizationRun,
        sequence: int,
        status: str,
        stage: str,
        progress_percent: int,
        status_message: str,
        claim_token: str,
        metrics: dict[str, object] | None = None,
    ) -> OptimizationRun:
        updated_run = replace(
            run,
            status=status,
            stage=stage,
            progress_percent=progress_percent,
            status_message=status_message,
            claim_token=claim_token,
            claimed_by=self.worker_id,
        )
        await self.schedule_repo.save_optimization_run(updated_run)
        await self.schedule_repo.append_optimization_run_event(
            OptimizationRunEvent(
                run_id=run.run_id,
                sequence=sequence,
                status=status,
                stage=stage,
                progress_percent=progress_percent,
                status_message=status_message,
                metrics=metrics,
                created_at=whenever.Instant.now().format_iso(),
            )
        )
        await self.schedule_repo.commit()
        return updated_run

    async def _finish_failure(
        self,
        claim: WorkerClaim,
        stage: str,
        status_message: str,
        error_details: str | None,
        failure_code: str,
        final_sequence: int,
    ) -> None:
        await self.schedule_repo.append_optimization_run_event(
            OptimizationRunEvent(
                run_id=claim.run.run_id,
                sequence=final_sequence,
                status=OptimizationRunStatus.FAILED.value,
                stage=stage,
                progress_percent=100,
                status_message=status_message,
                error_details=error_details,
                metrics={"failure_code": failure_code},
                created_at=whenever.Instant.now().format_iso(),
            )
        )
        await self.schedule_repo.release_optimization_run_claim(
            run_id=claim.run.run_id,
            claim_token=claim.claim_token,
            status=OptimizationRunStatus.FAILED.value,
            stage=stage,
            status_message=status_message,
            error_details=error_details,
            failure_code=failure_code,
        )
        await self.schedule_repo.commit()

    async def _build_snapshot(
        self,
        run: OptimizationRun,
        request: StartOptimizationRunRequest,
        base_schedule: Schedule,
        facility_context: FacilityScenarioContext,
        live_provider: IScenarioDataProvider,
    ) -> OptimizationSnapshot:
        decision_start = request.start_date
        decision_end = request.end_date or request.start_date
        policy_start = (
            whenever.Date.parse_common_iso(decision_start)
            .subtract(days=7)
            .format_common_iso()
        )
        policy_end = (
            whenever.Date.parse_common_iso(decision_end).add(days=7).format_common_iso()
        )

        rebased_schedule = base_schedule
        conflicts: list[PatchConflict] = []
        if request.staged_patches:
            rebased_schedule, conflicts = await self.schedule_repo.reapply_patches(
                base_schedule,
                list(request.staged_patches),
            )
        locked_assignments = [
            LockedAssignment(
                employee_id=patch.employee_id,
                shift_key=key,
                created_at=patch.created_at,
            )
            for patch in request.staged_patches
            if patch.to_shift_id is not None
            for key in [
                next(
                    (
                        shift_key
                        for shift_key in rebased_schedule.shift_assignments
                        if shift_key.facility_id == request.facility_id
                        and shift_key.shift_id == patch.to_shift_id
                    ),
                    None,
                )
            ]
            if key is not None
        ]

        # Warm up all live provider caches before snapshotting
        all_shifts = facility_context.shifts
        all_employees = await live_provider.get_all_employees()

        nurses_by_shift: dict[str, list[dict[str, object]]] = {}
        for shift in all_shifts:
            nurses = await live_provider.get_nurses_for_shift(shift)
            key_str = f"{shift.facility_id}:{shift.shift_id}"
            nurses_by_shift[key_str] = [_serialize_nurse(n) for n in nurses]

        hprd_req = await live_provider.get_hprd_requirements_for_facility(
            request.facility_id
        )

        accumulated_hours: dict[str, float] = {}
        for emp in all_employees:
            hours = await live_provider.get_accumulated_hours_for_pay_period(
                emp.employee_id
            )
            if hours:
                accumulated_hours[str(emp.employee_id)] = hours

        compensation: dict[str, dict[str, object]] = {}
        for emp in all_employees:
            comp = await live_provider.get_compensation_for_date(
                emp.employee_id,
                facility_context.shifts[0].shift_start_dt.date(),
            )
            if comp is not None:
                compensation[str(emp.employee_id)] = _serialize_compensation(comp)

        # Serialize HPRD requirements
        hprd_values: list[list[float]] = []
        for shift_id in (s.shift_id for s in all_shifts):
            row = []
            for role in [
                HprdEnforcedRole.RN,
                HprdEnforcedRole.LPN,
                HprdEnforcedRole.CNA,
            ]:
                row.append(hprd_req[shift_id, role])
            hprd_values.append(row)

        snapshot_payload: dict[str, object] = {
            "request": {
                "org_id": request.org_id,
                "facility_id": request.facility_id,
                "schedule_id": request.schedule_id,
                "base_schedule_version": request.base_schedule_version,
                "decision_start_date": decision_start,
                "decision_end_date": decision_end,
                "allow_overwrite": request.allow_overwrite,
                "persist_result": request.persist_result,
            },
            "settings": request.settings.__dict__,
            "settings_org_id": request.org_id,
            "patches": [patch.__dict__ for patch in request.staged_patches],
            "conflicts": [conflict.__dict__ for conflict in conflicts],
            "locked_assignments": [
                {
                    "employee_id": item.employee_id,
                    "facility_id": item.shift_key.facility_id,
                    "shift_id": item.shift_key.shift_id,
                    "created_at": item.created_at,
                    "source": item.source,
                }
                for item in locked_assignments
            ],
            "base_schedule": {
                "schedule_id": base_schedule.schedule_id,
                "schedule_version": base_schedule.schedule_version,
                "shift_assignments": {
                    json.dumps([key.facility_id, key.shift_id]): value
                    for key, value in base_schedule.shift_assignments.items()
                },
            },
            "facility_contexts": {
                str(request.facility_id): {
                    "config": _serialize_config(facility_context.config),
                    "shifts": [_serialize_shift(s) for s in facility_context.shifts],
                    "min_mandates": _serialize_mandates(facility_context.min_mandates),
                    "default_hprd_rn": facility_context.default_hprd_rn,
                    "default_hprd_cna": facility_context.default_hprd_cna,
                    "default_hprd_total": facility_context.default_hprd_total,
                }
            },
            "employees": [_serialize_employee(e) for e in all_employees],
            "nurses_by_shift": nurses_by_shift,
            "hprd_requirements": {
                str(request.facility_id): {
                    "values": hprd_values,
                }
            },
            "accumulated_hours": accumulated_hours,
            "compensation": compensation,
        }
        return OptimizationSnapshot(
            snapshot_id=uuid4().hex,
            run_id=run.run_id,
            org_id=run.org_id,
            facility_id=run.facility_id,
            schedule_id=run.schedule_id,
            base_schedule_version=run.base_schedule_version,
            decision_start_date=decision_start,
            decision_end_date=decision_end,
            policy_start_date=policy_start,
            policy_end_date=policy_end,
            payload=snapshot_payload,
            created_at=whenever.Instant.now().format_iso(),
        )

    def _request_from_run(self, run: OptimizationRun) -> StartOptimizationRunRequest:
        decision_start = run.decision_start_date or (
            run.started_at[:10] if run.started_at else "1970-01-01"
        )
        decision_end = run.decision_end_date or run.decision_start_date
        return StartOptimizationRunRequest(
            org_id=run.org_id,
            facility_id=run.facility_id,
            schedule_id=run.schedule_id,
            base_schedule_version=run.base_schedule_version,
            start_date=decision_start,
            end_date=decision_end,
            settings=run.settings or OptimizationSettings(),
            staged_patches=run.patches,
            persist_result=run.persist_result,
            client_request_id=run.client_request_id,
        )

    @staticmethod
    def _locked_assignments_from_snapshot(
        snapshot: OptimizationSnapshot,
    ) -> list[LockedAssignment]:
        locked_payload = snapshot.payload.get("locked_assignments")
        if not isinstance(locked_payload, list) or not locked_payload:
            return []

        locked_assignments = []
        for item in locked_payload:
            if not isinstance(item, dict):
                continue
            facility_id = item.get("facility_id")
            shift_id = item.get("shift_id")
            employee_id = item.get("employee_id")
            if (
                not isinstance(facility_id, int)
                or not isinstance(shift_id, int)
                or not isinstance(employee_id, int)
            ):
                continue
            created_at = item.get("created_at")
            source = item.get("source")
            locked_assignments.append(
                LockedAssignment(
                    employee_id=employee_id,
                    shift_key=ShiftKey(facility_id, shift_id),
                    created_at=created_at if isinstance(created_at, str) else None,
                    source=source if isinstance(source, str) else "snapshot",
                )
            )

        return locked_assignments


def _serialize_shift(shift: Shift) -> dict[str, object]:
    return {
        "org_id": shift.org_id,
        "facility_id": shift.facility_id,
        "shift_id": shift.shift_key.shift_id,
        "shift_number": shift.shift_number,
        "day_shift": shift.day_shift,
        "day_of_week": shift.day_of_week.name,
        "shift_start_iso": shift.shift_start_dt.format_common_iso(),
        "shift_end_iso": shift.shift_end_dt.format_common_iso(),
        "unit_id": shift.unit_id,
        "is_scheduled": shift.is_scheduled,
    }


def _serialize_employee(emp: Employee) -> dict[str, object]:
    return {
        "employee_id": emp.employee_id,
        "name": emp.name,
        "job_title": emp.job_title,
        "hire_date": emp.hire_date.format_common_iso(),
    }


def _serialize_nurse(nurse: Any) -> dict[str, object]:
    prefs = None
    if nurse.shift_custom_preferences:
        prefs = [
            {
                "preference_type": p.preference_type.value,
                "specific_value": p.specific_value,
                "penalty_weight": p.penalty_weight,
                "is_hard_block": p.is_hard_block,
            }
            for p in nurse.shift_custom_preferences
        ]
    return {
        "employee_id": nurse.employee_id,
        "available_hours_weekly": nurse.available_hours_weekly,
        "skills": nurse.skills,
        "shift_custom_preferences": prefs,
    }


def _serialize_config(config: FacilityConfig) -> dict[str, object]:
    return {
        "org_id": config.org_id,
        "facility_id": config.facility_id,
        "shifts_per_day": config.shifts_per_day,
        "overtime_threshold_hours_per_week": config.overtime_threshold_hours_per_week,
        "start_of_work_week_day": config.start_of_work_week_day.name,
        "start_of_work_day_time": config.start_of_work_day_time.format_common_iso(),
        "pay_period": config.pay_period.in_months_days()[1],
        "weekend_multiplier": config.weekend_multiplier,
        "night_shift_multiplier": config.night_shift_multiplier,
        "tz": config.tz,
        "default_hprd_rn": config.default_hprd_rn,
        "default_hprd_lpn": config.default_hprd_lpn,
        "default_hprd_cna": config.default_hprd_cna,
        "default_hprd_total": config.default_hprd_total,
        "min_rest_hours_between_shifts": config.min_rest_hours_between_shifts,
        "max_consecutive_work_days": config.max_consecutive_work_days,
        "max_total_hours_per_pay_period": config.max_total_hours_per_pay_period,
    }


def _serialize_mandates(mandates: MinMandates | None) -> dict[str, object] | None:
    if mandates is None:
        return None
    return {
        "min_rn_hprd": mandates.min_rn_hprd,
        "min_lpn_hprd": mandates.min_lpn_hprd,
        "min_cna_hprd": mandates.min_cna_hprd,
        "min_total_hprd": mandates.min_total_hprd,
        "min_staff_per_shift_rn": mandates.min_staff_per_shift_rn,
        "min_staff_per_shift_lpn": mandates.min_staff_per_shift_lpn,
        "min_staff_per_shift_cna": mandates.min_staff_per_shift_cna,
    }


def _serialize_compensation(comp: Any) -> dict[str, object]:
    return {
        "employee_id": comp.employee_id,
        "base_rate_effective": comp.base_rate_effective,
        "ot_multiplier": comp.ot_multiplier,
        "is_agency": comp.is_agency,
        "effective_start_date": comp.effective_start_date.format_common_iso(),
        "effective_end_date": (
            comp.effective_end_date.format_common_iso()
            if comp.effective_end_date
            else None
        ),
        "union_contract_id": comp.union_contract_id,
        "pay_grade_or_step": comp.pay_grade_or_step,
    }
