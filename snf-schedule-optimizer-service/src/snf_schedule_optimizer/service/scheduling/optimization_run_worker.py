from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from uuid import uuid4

import whenever

from snf_schedule_optimizer.api import StartOptimizationRunRequest
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IScheduleRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.models import (
    LockedAssignment,
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSettings,
    OptimizationSnapshot,
    PatchConflict,
    Schedule,
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
        renew_lease: (
            Callable[[str, str, str, str], Awaitable[bool]] | None
        ) = None,
    ) -> None:
        self.worker_id = worker_id
        self.schedule_repo = schedule_repo
        self.scheduler_facade = scheduler_facade
        self.renew_lease = renew_lease

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
        lease_expires_at = whenever.Instant.now().add(seconds=LEASE_SECONDS).format_iso()
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
                status="running",
                stage="snapshotting",
                progress_percent=5,
                status_message="Building optimization snapshot",
                claim_token=claim.claim_token,
            )

            request = self._request_from_run(current_run)
            base_schedule = await self.schedule_repo.get_schedule(
                ScheduleLookupKey(current_run.org_id, current_run.schedule_id)
            )
            if base_schedule is None:
                raise ValueError("Base schedule not found for claimed run.")

            snapshot = await self._build_snapshot(current_run, request, base_schedule)
            await self.schedule_repo.save_optimization_snapshot(snapshot)
            current_run = replace(
                current_run,
                snapshot_id=snapshot.snapshot_id,
                policy_start_date=snapshot.policy_start_date,
                policy_end_date=snapshot.policy_end_date,
            )
            await self.schedule_repo.save_optimization_run(current_run)
            await self.schedule_repo.commit()

            current_run = await self._publish_progress(
                current_run,
                sequence=2,
                status="running",
                stage="indexing",
                progress_percent=15,
                status_message="Indexing scenario data",
                claim_token=claim.claim_token,
                metrics={"snapshot_id": snapshot.snapshot_id},
            )

            current_run = await self._publish_progress(
                current_run,
                sequence=3,
                status="running",
                stage="building_model",
                progress_percent=30,
                status_message="Building optimization model",
                claim_token=claim.claim_token,
            )

            facility_context = await self.scheduler_facade._build_optimization_context(
                org_id=request.org_id,
                facility_id=request.facility_id,
                start_date=request.start_date,
                end_date=request.end_date or request.start_date,
                optimization_settings=request.settings,
            )

            current_run = await self._publish_progress(
                current_run,
                sequence=4,
                status="running",
                stage="solving",
                progress_percent=55,
                status_message="Solving staffing plan",
                claim_token=claim.claim_token,
            )

            locked_schedule = self._locked_schedule_from_snapshot(snapshot, base_schedule)
            result = await self.scheduler_facade.optimize_schedule(
                org_id=request.org_id,
                facility_contexts={request.facility_id: facility_context},
                preference_weights=request.settings.to_preference_weights(),
                pay_period_start=facility_context.shifts[0].shift_start_dt.start_of_day().to_instant(),
                optimization_settings=request.settings,
                pinned_schedule=locked_schedule,
            )

            if not result.is_success or result.schedule is None:
                await self._finish_failure(
                    claim,
                    stage="failed",
                    status_message="Optimization failed",
                    error_details=result.error_details,
                    failure_code="solver_infeasible",
                    final_sequence=5,
                )
                return

            current_run = await self._publish_progress(
                current_run,
                sequence=5,
                status="running",
                stage="analyzing",
                progress_percent=80,
                status_message="Analyzing staffing plan",
                claim_token=claim.claim_token,
            )

            latest_version = await self.schedule_repo.get_latest_schedule_version(
                request.org_id,
                request.schedule_id,
            )
            next_version = (latest_version or 0) + 1

            persisted_schedule = Schedule(
                org_id=request.org_id,
                facility_id=request.facility_id,
                schedule_id=request.schedule_id,
                schedule_lineage_id=request.schedule_id,
                schedule_version=next_version,
                shift_assignments=result.schedule.shift_assignments,
                start_date=request.start_date,
                end_date=request.end_date or request.start_date,
                latest_optimization=result.summary,
                latest_optimization_stats=result.stats,
                latest_optimization_financials=result.financials,
                updated_at=whenever.Instant.now().format_iso(),
            )

            current_run = await self._publish_progress(
                current_run,
                sequence=6,
                status="running",
                stage="publishing",
                progress_percent=92,
                status_message="Publishing optimized schedule",
                claim_token=claim.claim_token,
            )

            if request.persist_result:
                await self.schedule_repo.save_schedule(persisted_schedule)

            final_run = replace(
                current_run,
                status="completed",
                stage="completed",
                progress_percent=100,
                status_message="Optimization completed",
                completed_at=whenever.Instant.now().format_iso(),
                result_schedule_id=(
                    persisted_schedule.schedule_id if request.persist_result else None
                ),
                result_schedule_version=(
                    persisted_schedule.schedule_version if request.persist_result else None
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
                    status="completed",
                    stage="completed",
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
                status="completed",
                stage="completed",
                status_message="Optimization completed",
            )
            await self.schedule_repo.commit()
        except Exception as exc:
            await self.schedule_repo.rollback()
            try:
                await self._finish_failure(
                    claim,
                    stage="failed",
                    status_message="Optimization worker failed",
                    error_details=str(exc),
                    failure_code="worker_error",
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
            renewed = await self._renew_lease(claim.run.run_id, claim.claim_token, now, lease)
            if not renewed:
                return

    async def _renew_lease(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool:
        if self.renew_lease is not None:
            return await self.renew_lease(
                run_id,
                claim_token,
                heartbeat_at,
                lease_expires_at,
            )
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
                status="failed",
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
            status="failed",
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
    ) -> OptimizationSnapshot:
        decision_start = request.start_date
        decision_end = request.end_date or request.start_date
        policy_start = whenever.Date.parse_common_iso(decision_start).subtract(days=7).format_common_iso()
        policy_end = whenever.Date.parse_common_iso(decision_end).add(days=7).format_common_iso()

        rebased_schedule = base_schedule
        conflicts: list[PatchConflict] = []
        if request.staged_patches:
            rebased_schedule, conflicts = await self.schedule_repo.reapply_patches(
                base_schedule,
                list(request.staged_patches),
            )
        locked_assignments = [
            LockedAssignment(employee_id=patch.employee_id, shift_key=key, created_at=patch.created_at)
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
    def _locked_schedule_from_snapshot(
        snapshot: OptimizationSnapshot,
        base_schedule: Schedule,
    ) -> Schedule | None:
        locked_payload = snapshot.payload.get("locked_assignments")
        if not isinstance(locked_payload, list) or not locked_payload:
            return None

        locked_assignments = defaultdict(list)
        for item in locked_payload:
            if not isinstance(item, dict):
                continue
            facility_id = item.get("facility_id")
            shift_id = item.get("shift_id")
            employee_id = item.get("employee_id")
            if not isinstance(facility_id, int) or not isinstance(shift_id, int) or not isinstance(employee_id, int):
                continue
            locked_assignments[(facility_id, shift_id)].append(employee_id)

        shift_assignments = {
            key: list(dict.fromkeys(locked_assignments.get((key.facility_id, key.shift_id), employees)))
            for key, employees in base_schedule.shift_assignments.items()
        }
        return replace(base_schedule, shift_assignments=shift_assignments)
