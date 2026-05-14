import json
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

import whenever
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IScheduleRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.models import (
    OptimizationRun,
    OptimizationRunEvent,
    OptimizationSettings,
    OptimizationSnapshot,
    OptimizationSummary,
    PatchConflict,
    Schedule,
    ShiftAssignmentsType,
    ShiftKey,
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
from snf_schedule_optimizer.sqlalchemy_models.optimization_snapshot import (
    OptimizationSnapshotModel,
)
from snf_schedule_optimizer.sqlalchemy_models.schedule_assignment import (
    ScheduleAssignmentModel,
)
from snf_schedule_optimizer.sqlalchemy_models.schedule_record import ScheduleRecordModel
from snf_schedule_optimizer.sqlalchemy_models.shift import ShiftModel


class SQLScheduleRepo(IScheduleRepo):
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_schedule(
        self,
        schedule_lookup: ScheduleLookupKey,
    ) -> Schedule | None:
        """
        Fetches assignments from the DB and reconstructs the Domain Schedule object.
        """
        stmt = select(ScheduleAssignmentModel).where(
            ScheduleAssignmentModel.org_id == schedule_lookup.org_id,
            ScheduleAssignmentModel.schedule_id == schedule_lookup.schedule_id,
        )

        results: Sequence[ScheduleAssignmentModel] | None = (
            await self.db_session.scalars(stmt)
        ).all()

        if not results:
            return None

        # Map DB Rows -> Domain Object
        # Structure: dict[shift_id, list[employee_id]]
        assignments: ShiftAssignmentsType = defaultdict(list)

        for row in results:
            assignments[ShiftKey(row.facility_id, row.shift_id)].append(row.employee_id)

        schedule_record = await self.db_session.get(
            ScheduleRecordModel, schedule_lookup.schedule_id
        )
        latest_run = await self.get_latest_completed_optimization_run(
            schedule_lookup.org_id,
            schedule_record.facility_id if schedule_record else 0,
            schedule_lookup.schedule_id,
        )

        return Schedule(
            org_id=schedule_lookup.org_id,
            facility_id=schedule_record.facility_id if schedule_record else None,
            schedule_id=schedule_lookup.schedule_id,
            schedule_lineage_id=schedule_lookup.schedule_id,
            schedule_version=schedule_record.version if schedule_record else 1,
            shift_assignments=assignments,
            start_date=schedule_record.start_date if schedule_record else None,
            end_date=schedule_record.end_date if schedule_record else None,
            latest_optimization=latest_run.summary if latest_run else None,
            latest_optimization_stats=latest_run.stats if latest_run else None,
            latest_optimization_financials=latest_run.financials if latest_run else None,
            updated_at=schedule_record.updated_at.isoformat() if schedule_record else None,
        )

    async def get_schedule_for_month(
        self,
        org_id: int,
        facility_id: int | None,
        start_date: str,
    ) -> Schedule | None:
        record_stmt = select(ScheduleRecordModel).where(
            ScheduleRecordModel.org_id == org_id,
            ScheduleRecordModel.start_date <= start_date,
            ScheduleRecordModel.end_date >= start_date,
        )
        if facility_id is not None:
            record_stmt = record_stmt.where(ScheduleRecordModel.facility_id == facility_id)
        record_stmt = record_stmt.order_by(
            ScheduleRecordModel.updated_at.desc(),
            ScheduleRecordModel.schedule_id.desc(),
        )
        schedule_record = (await self.db_session.scalars(record_stmt)).first()
        if schedule_record is None:
            return None

        stmt = select(ScheduleAssignmentModel).where(
            ScheduleAssignmentModel.org_id == org_id,
            ScheduleAssignmentModel.schedule_id == schedule_record.schedule_id,
        )
        results = (await self.db_session.scalars(stmt)).all()
        latest_run = await self.get_latest_completed_optimization_run(
            org_id,
            schedule_record.facility_id,
            schedule_record.schedule_id,
        )

        assignments: ShiftAssignmentsType = defaultdict(list)
        for row in results:
            assignments[ShiftKey(row.facility_id, row.shift_id)].append(row.employee_id)

        return Schedule(
            org_id=org_id,
            facility_id=schedule_record.facility_id,
            schedule_id=schedule_record.schedule_id,
            schedule_lineage_id=schedule_record.schedule_id,
            schedule_version=schedule_record.version,
            shift_assignments=assignments,
            start_date=schedule_record.start_date,
            end_date=schedule_record.end_date,
            latest_optimization=latest_run.summary if latest_run else None,
            latest_optimization_stats=latest_run.stats if latest_run else None,
            latest_optimization_financials=latest_run.financials if latest_run else None,
            updated_at=schedule_record.updated_at.isoformat(),
        )

    async def save_schedule(self, schedule: Schedule) -> None:
        if schedule.schedule_id is None:
            raise ValueError("schedule_id is required to persist a schedule")

        facility_ids = {shift_key.facility_id for shift_key in schedule.shift_assignments}
        facility_id = schedule.facility_id
        if facility_id is None:
            if len(facility_ids) != 1:
                raise ValueError("schedule.facility_id is required for persistence")
            facility_id = next(iter(facility_ids))

        shift_ids = [shift_key.shift_id for shift_key in schedule.shift_assignments]
        start_date = schedule.start_date or ""
        end_date = schedule.end_date or ""
        if shift_ids and (not start_date or not end_date):
            shift_stmt = select(ShiftModel).where(
                ShiftModel.org_id == schedule.org_id,
                ShiftModel.facility_id == facility_id,
                ShiftModel.id.in_(shift_ids),
            )
            shift_models = (await self.db_session.scalars(shift_stmt)).all()
            if shift_models:
                shift_dates = sorted(
                    shift.shift_start_dt.to_tz("America/New_York").date().format_common_iso()
                    for shift in shift_models
                )
                start_date = shift_dates[0]
                end_date = shift_dates[-1]

        existing_record = (
            await self.db_session.scalars(
                select(ScheduleRecordModel).where(
                    ScheduleRecordModel.org_id == schedule.org_id,
                    ScheduleRecordModel.schedule_id == schedule.schedule_id,
                )
            )
        ).first()
        if existing_record is None:
            self.db_session.add(
                ScheduleRecordModel(
                    schedule_id=schedule.schedule_id,
                    org_id=schedule.org_id,
                    facility_id=facility_id,
                    start_date=start_date,
                    end_date=end_date,
                    version=schedule.schedule_version,
                )
            )
        else:
            existing_record.facility_id = facility_id
            existing_record.start_date = start_date
            existing_record.end_date = end_date
            existing_record.version = schedule.schedule_version

        await self.db_session.execute(
            delete(ScheduleAssignmentModel).where(
                ScheduleAssignmentModel.org_id == schedule.org_id,
                ScheduleAssignmentModel.schedule_id == schedule.schedule_id,
            )
        )

        assignment_id = 1
        for shift_key, employee_ids in schedule.shift_assignments.items():
            for employee_id in employee_ids:
                self.db_session.add(
                    ScheduleAssignmentModel(
                        schedule_id=schedule.schedule_id,
                        assignment_id=assignment_id,
                        org_id=schedule.org_id,
                        facility_id=shift_key.facility_id,
                        shift_id=shift_key.shift_id,
                        employee_id=employee_id,
                    )
                )
                assignment_id += 1

    async def next_schedule_id(self, org_id: int) -> int:
        stmt = select(func.max(ScheduleRecordModel.schedule_id)).where(
            ScheduleRecordModel.org_id == org_id
        )
        current_max = await self.db_session.scalar(stmt)
        if current_max is None:
            current_max = await self.db_session.scalar(
                select(func.max(ScheduleAssignmentModel.schedule_id)).where(
                    ScheduleAssignmentModel.org_id == org_id
                )
            )
        return (current_max or 0) + 1

    async def get_latest_schedule_version(self, org_id: int, schedule_id: int) -> int | None:
        stmt = select(ScheduleRecordModel.version).where(
            ScheduleRecordModel.org_id == org_id,
            ScheduleRecordModel.schedule_id == schedule_id,
        )
        result = await self.db_session.scalar(stmt)
        return int(result) if result is not None else None

    async def reapply_patches(
        self,
        schedule: Schedule,
        patches: list[StagedSchedulePatch],
    ) -> tuple[Schedule, list[PatchConflict]]:
        shift_assignments: ShiftAssignmentsType = defaultdict(list)
        for shift_key, employee_ids in schedule.shift_assignments.items():
            shift_assignments[shift_key] = list(employee_ids)

        conflicts: list[PatchConflict] = []
        for patch in patches:
            if patch.from_shift_id == patch.to_shift_id:
                continue
            current_from_key = next(
                (
                    key
                    for key in shift_assignments
                    if key.facility_id == schedule.facility_id
                    and key.shift_id == patch.from_shift_id
                ),
                None,
            )
            current_to_key = next(
                (
                    key
                    for key in shift_assignments
                    if key.facility_id == schedule.facility_id
                    and key.shift_id == patch.to_shift_id
                ),
                None,
            )
            if patch.from_shift_id is not None and current_from_key is None:
                conflicts.append(
                    PatchConflict(
                        patch_id=patch.patch_id,
                        employee_id=patch.employee_id,
                        employee_name=patch.employee_name,
                        from_shift_id=patch.from_shift_id,
                        to_shift_id=patch.to_shift_id,
                        reason="Original assignment no longer exists.",
                    )
                )
                continue
            if patch.to_shift_id is not None and current_to_key is None:
                conflicts.append(
                    PatchConflict(
                        patch_id=patch.patch_id,
                        employee_id=patch.employee_id,
                        employee_name=patch.employee_name,
                        from_shift_id=patch.from_shift_id,
                        to_shift_id=patch.to_shift_id,
                        reason="Target shift is no longer available.",
                    )
                )
                continue

            if current_from_key is not None and patch.employee_id not in shift_assignments[current_from_key]:
                conflicts.append(
                    PatchConflict(
                        patch_id=patch.patch_id,
                        employee_id=patch.employee_id,
                        employee_name=patch.employee_name,
                        from_shift_id=patch.from_shift_id,
                        to_shift_id=patch.to_shift_id,
                        reason="Employee is no longer assigned to the original shift.",
                    )
                )
                continue

            if current_from_key is not None:
                shift_assignments[current_from_key].remove(patch.employee_id)
            if current_to_key is not None and patch.employee_id not in shift_assignments[current_to_key]:
                shift_assignments[current_to_key].append(patch.employee_id)

        return (
            Schedule(
                org_id=schedule.org_id,
                facility_id=schedule.facility_id,
                schedule_id=schedule.schedule_id,
                schedule_lineage_id=schedule.schedule_lineage_id,
                schedule_version=schedule.schedule_version,
                shift_assignments=dict(shift_assignments),
                start_date=schedule.start_date,
                end_date=schedule.end_date,
                latest_optimization=schedule.latest_optimization,
                latest_optimization_stats=schedule.latest_optimization_stats,
                latest_optimization_financials=schedule.latest_optimization_financials,
                updated_at=schedule.updated_at,
            ),
            conflicts,
        )

    async def save_optimization_run(self, run: OptimizationRun) -> None:
        existing = await self.db_session.get(OptimizationRunModel, run.run_id)
        payload = {
            "org_id": run.org_id,
            "facility_id": run.facility_id,
            "schedule_id": run.schedule_id,
            "base_schedule_version": run.base_schedule_version,
            "result_schedule_id": run.result_schedule_id,
            "result_schedule_version": run.result_schedule_version,
            "status": run.status,
            "stage": run.stage,
            "progress_percent": run.progress_percent,
            "status_message": run.status_message,
            "error_details": run.error_details,
            "client_request_id": run.client_request_id,
            "patches_json": json.dumps([self._patch_to_dict(patch) for patch in run.patches]),
            "persist_result": run.persist_result,
            "start_date": run.decision_start_date or "1970-01-01",
            "end_date": run.decision_end_date or run.decision_start_date or "1970-01-01",
            "policy_start_date": run.policy_start_date,
            "policy_end_date": run.policy_end_date,
            "snapshot_id": run.snapshot_id,
            "claimed_by": run.claimed_by,
            "claim_token": run.claim_token,
            "attempt_count": run.attempt_count,
            "failure_code": run.failure_code,
            "termination_reason": run.termination_reason,
            "settings_json": self._dump_settings(run.settings) if run.settings else None,
            "summary_json": json.dumps(self._summary_to_dict(run.summary)) if run.summary else None,
            "stats_json": json.dumps(self._stats_to_dict(run.stats)) if run.stats else None,
            "financials_json": json.dumps(self._financials_to_dict(run.financials)) if run.financials else None,
        }
        if existing is None:
            model = OptimizationRunModel(
                run_id=run.run_id,
                **payload,
            )
            if run.started_at is not None:
                model.started_at = whenever.Instant.parse_iso(run.started_at).py_datetime()
            if run.completed_at is not None:
                model.completed_at = whenever.Instant.parse_iso(run.completed_at).py_datetime()
            model.heartbeat_at = (
                whenever.Instant.parse_iso(run.heartbeat_at).py_datetime()
                if run.heartbeat_at is not None
                else None
            )
            model.lease_expires_at = (
                whenever.Instant.parse_iso(run.lease_expires_at).py_datetime()
                if run.lease_expires_at is not None
                else None
            )
            self.db_session.add(model)
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            if run.started_at is not None:
                existing.started_at = whenever.Instant.parse_iso(run.started_at).py_datetime()
            if run.completed_at is not None:
                existing.completed_at = whenever.Instant.parse_iso(run.completed_at).py_datetime()
            if run.heartbeat_at is not None:
                existing.heartbeat_at = whenever.Instant.parse_iso(run.heartbeat_at).py_datetime()
            if run.lease_expires_at is not None:
                existing.lease_expires_at = whenever.Instant.parse_iso(run.lease_expires_at).py_datetime()
            existing.cancel_requested_at = existing.cancel_requested_at

    async def get_optimization_run_by_client_request(
        self,
        org_id: int,
        facility_id: int,
        schedule_id: int,
        client_request_id: str,
    ) -> OptimizationRun | None:
        stmt = (
            select(OptimizationRunModel)
            .where(
                OptimizationRunModel.org_id == org_id,
                OptimizationRunModel.facility_id == facility_id,
                OptimizationRunModel.schedule_id == schedule_id,
                OptimizationRunModel.client_request_id == client_request_id,
            )
            .order_by(OptimizationRunModel.updated_at.desc())
        )
        model = (await self.db_session.scalars(stmt)).first()
        return self._map_run(model) if model is not None else None

    async def get_optimization_run(self, run_id: str) -> OptimizationRun | None:
        model = await self.db_session.get(OptimizationRunModel, run_id)
        if model is None:
            return None
        return self._map_run(model)

    async def get_active_optimization_run(
        self,
        org_id: int,
        facility_id: int,
        schedule_id: int,
    ) -> OptimizationRun | None:
        stmt = (
            select(OptimizationRunModel)
            .where(
                OptimizationRunModel.org_id == org_id,
                OptimizationRunModel.facility_id == facility_id,
                OptimizationRunModel.schedule_id == schedule_id,
                OptimizationRunModel.status.in_(["queued", "running"]),
            )
            .order_by(OptimizationRunModel.updated_at.desc())
        )
        model = (await self.db_session.scalars(stmt)).first()
        return self._map_run(model) if model is not None else None

    async def append_optimization_run_event(self, event: OptimizationRunEvent) -> None:
        self.db_session.add(
            OptimizationRunEventModel(
                run_id=event.run_id,
                sequence=event.sequence,
                status=event.status,
                stage=event.stage,
                progress_percent=event.progress_percent,
                status_message=event.status_message,
                error_details=event.error_details,
                metrics_json=json.dumps(event.metrics) if event.metrics is not None else None,
            )
        )

    async def list_optimization_run_events(
        self,
        run_id: str,
    ) -> list[OptimizationRunEvent]:
        stmt = (
            select(OptimizationRunEventModel)
            .where(OptimizationRunEventModel.run_id == run_id)
            .order_by(OptimizationRunEventModel.sequence.asc())
        )
        models = (await self.db_session.scalars(stmt)).all()
        return [self._map_run_event(model) for model in models]

    async def claim_next_queued_optimization_run(
        self,
        worker_id: str,
        claim_token: str,
        lease_expires_at: str,
    ) -> OptimizationRun | None:
        lease_cutoff = whenever.Instant.now().py_datetime()
        stmt = (
            select(OptimizationRunModel)
            .where(
                or_(
                    OptimizationRunModel.status == "queued",
                    (
                        OptimizationRunModel.status == "running"
                    )
                    & (
                        OptimizationRunModel.lease_expires_at.is_not(None)
                    )
                    & (OptimizationRunModel.lease_expires_at < lease_cutoff),
                )
            )
            .order_by(OptimizationRunModel.updated_at.asc())
        )
        model = (await self.db_session.scalars(stmt)).first()
        if model is None:
            return None

        now = whenever.Instant.now().py_datetime()
        model.status = "running"
        model.stage = "queued"
        model.status_message = "Claimed by worker"
        model.claimed_by = worker_id
        model.claim_token = claim_token
        model.attempt_count += 1
        model.heartbeat_at = now
        model.lease_expires_at = whenever.Instant.parse_iso(lease_expires_at).py_datetime()
        if model.started_at is None:
            model.started_at = now
        await self.db_session.flush()
        return self._map_run(model)

    async def renew_optimization_run_lease(
        self,
        run_id: str,
        claim_token: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> bool:
        model = await self.db_session.get(OptimizationRunModel, run_id)
        if model is None or model.claim_token != claim_token:
            return False
        model.heartbeat_at = whenever.Instant.parse_iso(heartbeat_at).py_datetime()
        model.lease_expires_at = whenever.Instant.parse_iso(lease_expires_at).py_datetime()
        return True

    async def release_optimization_run_claim(
        self,
        run_id: str,
        claim_token: str,
        status: str,
        stage: str,
        status_message: str,
        error_details: str | None = None,
        failure_code: str | None = None,
    ) -> bool:
        model = await self.db_session.get(OptimizationRunModel, run_id)
        if model is None or model.claim_token != claim_token:
            return False
        model.status = status
        model.stage = stage
        model.status_message = status_message
        model.error_details = error_details
        model.failure_code = failure_code
        model.claimed_by = None
        model.claim_token = None
        model.lease_expires_at = None
        model.heartbeat_at = whenever.Instant.now().py_datetime()
        if status in {"completed", "failed"}:
            model.completed_at = whenever.Instant.now().py_datetime()
        return True

    async def save_optimization_snapshot(self, snapshot: OptimizationSnapshot) -> None:
        existing = await self.db_session.get(OptimizationSnapshotModel, snapshot.snapshot_id)
        payload_json = json.dumps(snapshot.payload)
        if existing is None:
            self.db_session.add(
                OptimizationSnapshotModel(
                    snapshot_id=snapshot.snapshot_id,
                    run_id=snapshot.run_id,
                    org_id=snapshot.org_id,
                    facility_id=snapshot.facility_id,
                    schedule_id=snapshot.schedule_id,
                    base_schedule_version=snapshot.base_schedule_version,
                    decision_start_date=snapshot.decision_start_date,
                    decision_end_date=snapshot.decision_end_date,
                    policy_start_date=snapshot.policy_start_date,
                    policy_end_date=snapshot.policy_end_date,
                    payload_json=payload_json,
                )
            )
            return
        existing.run_id = snapshot.run_id
        existing.org_id = snapshot.org_id
        existing.facility_id = snapshot.facility_id
        existing.schedule_id = snapshot.schedule_id
        existing.base_schedule_version = snapshot.base_schedule_version
        existing.decision_start_date = snapshot.decision_start_date
        existing.decision_end_date = snapshot.decision_end_date
        existing.policy_start_date = snapshot.policy_start_date
        existing.policy_end_date = snapshot.policy_end_date
        existing.payload_json = payload_json

    async def get_optimization_snapshot(self, snapshot_id: str) -> OptimizationSnapshot | None:
        model = await self.db_session.get(OptimizationSnapshotModel, snapshot_id)
        if model is None:
            return None
        return OptimizationSnapshot(
            snapshot_id=model.snapshot_id,
            run_id=model.run_id,
            org_id=model.org_id,
            facility_id=model.facility_id,
            schedule_id=model.schedule_id,
            base_schedule_version=model.base_schedule_version,
            decision_start_date=model.decision_start_date,
            decision_end_date=model.decision_end_date,
            policy_start_date=model.policy_start_date,
            policy_end_date=model.policy_end_date,
            payload=cast(dict[str, object], json.loads(model.payload_json)),
            created_at=model.created_at.isoformat(),
        )

    async def get_latest_completed_optimization_run(
        self,
        org_id: int,
        facility_id: int,
        schedule_id: int,
    ) -> OptimizationRun | None:
        stmt = (
            select(OptimizationRunModel)
            .where(
                OptimizationRunModel.org_id == org_id,
                OptimizationRunModel.facility_id == facility_id,
                OptimizationRunModel.schedule_id == schedule_id,
                OptimizationRunModel.status == "completed",
            )
            .order_by(OptimizationRunModel.updated_at.desc())
        )
        model = (await self.db_session.scalars(stmt)).first()
        return self._map_run(model) if model is not None else None

    async def commit(self) -> None:
        await self.db_session.commit()

    @staticmethod
    def _incentive_cost(financials: ScheduleFinancialReport | None) -> float | None:
        if financials is None:
            return None
        return sum(breakdown.bonuses for breakdown in financials.breakdown_per_facility.values())

    @staticmethod
    def _overtime_cost(financials: ScheduleFinancialReport | None) -> float | None:
        if financials is None:
            return None
        return sum(
            breakdown.overtime_cost for breakdown in financials.breakdown_per_facility.values()
        )

    @staticmethod
    def _regular_cost(financials: ScheduleFinancialReport | None) -> float | None:
        if financials is None:
            return None
        return sum(
            breakdown.regular_cost for breakdown in financials.breakdown_per_facility.values()
        )

    @staticmethod
    def _patch_to_dict(patch: StagedSchedulePatch) -> dict[str, object]:
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

    @staticmethod
    def _patch_from_dict(payload: dict[str, object]) -> StagedSchedulePatch:
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

    @staticmethod
    def _dump_settings(settings: OptimizationSettings) -> str:
        return json.dumps(
            {
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
        )

    @staticmethod
    def _summary_to_dict(summary: OptimizationSummary | None) -> dict[str, object] | None:
        if summary is None:
            return None
        return {
            "assignments_changed": summary.assignments_changed,
            "total_assignments": summary.total_assignments,
            "covered_shifts": summary.covered_shifts,
            "uncovered_shifts": summary.uncovered_shifts,
            "completed_at": summary.completed_at,
            "applied_settings": json.loads(SQLScheduleRepo._dump_settings(summary.applied_settings)),
        }

    @staticmethod
    def _stats_to_dict(stats: ScheduleOptimizationStats | None) -> dict[str, object] | None:
        if stats is None:
            return None
        return {
            "execution_time_ms": stats.execution_time_ms,
            "total_variables": stats.total_variables,
            "total_constraints": stats.total_constraints,
            "objective_value": stats.objective_value,
        }

    @staticmethod
    def _financials_to_dict(financials: ScheduleFinancialReport | None) -> dict[str, object] | None:
        if financials is None:
            return None
        return {
            "total_enterprise_cost": financials.total_enterprise_cost,
            "total_incentive_cost": SQLScheduleRepo._incentive_cost(financials) or 0.0,
            "total_overtime_cost": SQLScheduleRepo._overtime_cost(financials) or 0.0,
            "regular_pay_cost": SQLScheduleRepo._regular_cost(financials) or 0.0,
        }

    def _map_run(self, model: OptimizationRunModel) -> OptimizationRun:
        stats_payload = (
            cast(dict[str, Any], json.loads(model.stats_json)) if model.stats_json else None
        )
        summary_payload = (
            cast(dict[str, Any], json.loads(model.summary_json)) if model.summary_json else None
        )
        settings_payload = (
            cast(dict[str, Any], json.loads(model.settings_json)) if model.settings_json else None
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
                total_enterprise_cost=float(financials_payload.get("total_enterprise_cost", 0.0)),
                breakdown_per_facility={
                    model.facility_id: CostBreakdown(
                        regular_cost=float(financials_payload.get("regular_pay_cost", 0.0)),
                        overtime_cost=float(financials_payload.get("total_overtime_cost", 0.0)),
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
                applied_settings=OptimizationSettings(**summary_payload.get("applied_settings", {})),
            )
            if summary_payload
            else None,
            patches=tuple(
                self._patch_from_dict(payload)
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
            lease_expires_at=model.lease_expires_at.isoformat() if model.lease_expires_at else None,
            heartbeat_at=model.heartbeat_at.isoformat() if model.heartbeat_at else None,
            attempt_count=model.attempt_count,
            failure_code=model.failure_code,
            termination_reason=model.termination_reason,
        )

    @staticmethod
    def _map_run_event(model: OptimizationRunEventModel) -> OptimizationRunEvent:
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
