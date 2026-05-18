import asyncio
import base64
import logging
from collections.abc import AsyncIterator
from datetime import date, timedelta
from typing import Any, cast

import whenever
from connectrpc.request import RequestContext
from returns.result import Failure, Result, Success, safe
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from that_depends import container_context
from that_depends.providers.context_resources import ContextScopes, SupportsContext

from snf_schedule_optimizer.api import (
    MoveEmployeeRequest,
    OptimizeScheduleRequest,
    StartOptimizationRunRequest,
)
from snf_schedule_optimizer.api.grpc.scheduler_mappers import (
    decode_staged_patches,
    map_conflict,
    map_financials_from_values,
    map_monthly_schedule,
    map_optimize_response,
    map_run,
    map_settings,
    map_stats_from_values,
    map_summary,
    map_validation_response,
)
from snf_schedule_optimizer.domain.exceptions import (
    DataIntegrityError,
    SecurityError,
)
from snf_schedule_optimizer.generated.scheduling.v1 import (
    scheduling_connect,
    scheduling_pb2,
)
from snf_schedule_optimizer.generated.scheduling.v1 import (
    scheduling_pb2 as scheduling_dot_v1_dot_scheduling__pb2,
)
from snf_schedule_optimizer.generated.scheduling.v1.scheduling_pb2 import (
    GetAllOrgFacilitiesRequest,
    GetAllOrgFacilitiesResponse,
)
from snf_schedule_optimizer.infrastructure.composition import (
    IFacilityContainer,
    ISchedulerContainer,
    build_facility_container,
    build_repos_container,
    build_scheduler_container,
)
from snf_schedule_optimizer.infrastructure.sqid_converter import (
    DEMO_ID_ALIASES,
    IIdObfuscator,
)
from snf_schedule_optimizer.infrastructure.tracing import get_tracer
from snf_schedule_optimizer.models import OptimizationRun
from snf_schedule_optimizer.persistence.tenant import set_current_org_id
from snf_schedule_optimizer.service.facility.facility_facade import FacilityFacade
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacadePort,
)

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


@safe
def _decode(obfuscator: IIdObfuscator, val: str) -> int:
    return int(obfuscator.decode(val))


def get_internal_id(
    obfuscator: IIdObfuscator,
    val: str,
    label: str,
    required: bool = True,
) -> Result[int | None, str]:
    if not val:
        return Success(None) if not required else Failure(f"Missing {label} ID.")
    return _decode(obfuscator, val).alt(lambda _: f"Invalid {label} ID format.")


class SchedulingServiceHandler(scheduling_connect.SchedulingService):
    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
        id_obfuscator: IIdObfuscator,
        read_session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        self.engine = engine
        self.session_factory = session_factory
        self.id_obfuscator = id_obfuscator
        self._repos_container = build_repos_container(self.engine, self.session_factory, read_session_factory)
        self._scheduler_container = build_scheduler_container(self._repos_container)
        self._facility_container = build_facility_container(self._repos_container)

    def _build_scheduler_container(self) -> type[ISchedulerContainer]:
        return self._scheduler_container

    def _build_facility_container(self) -> type[IFacilityContainer]:
        return self._facility_container

    def _scheduler_context(
        self, scheduler_container: type[ISchedulerContainer]
    ) -> SupportsContext[Any]:
        return scheduler_container  # type: ignore[return-value]

    def _facility_context(
        self, facility_container: type[IFacilityContainer]
    ) -> SupportsContext[Any]:
        return facility_container  # type: ignore[return-value]

    async def _validate_tenant_access(
        self, org_id: int, facility_id: int | None
    ) -> None:
        facility_container = self._build_facility_container()
        async with container_context(
            self._facility_context(facility_container),
            scope=ContextScopes.REQUEST,
        ):
            facility_facade = await facility_container.facility_facade.resolve()
            configs = await facility_facade.get_all_org_facilities(org_id)
            if not configs:
                raise SecurityError(
                    f"Organization {org_id} not found or access denied."
                )
            if facility_id is not None and not any(
                c.facility_id == facility_id for c in configs
            ):
                raise SecurityError(
                    f"Facility {facility_id} does not belong to org {org_id}."
                )
        set_current_org_id(org_id)

    async def get_all_org_facilities(
        self,
        request: scheduling_dot_v1_dot_scheduling__pb2.GetAllOrgFacilitiesRequest,
        ctx: RequestContext[GetAllOrgFacilitiesRequest, GetAllOrgFacilitiesResponse],
    ) -> scheduling_dot_v1_dot_scheduling__pb2.GetAllOrgFacilitiesResponse:
        facility_container = self._build_facility_container()
        async with container_context(
            self._facility_context(facility_container),
            scope=ContextScopes.REQUEST,
        ):
            facility_facade: FacilityFacade = (
                await facility_container.facility_facade.resolve()
            )
            facility_configs = await facility_facade.get_all_system_facilities()
        org_facs = [
            scheduling_dot_v1_dot_scheduling__pb2.OrgFacility(
                org_id=DEMO_ID_ALIASES.get(
                    facility.org_id,
                    self.id_obfuscator.encode(facility.org_id),
                ),
                facility_id=DEMO_ID_ALIASES.get(
                    facility.facility_id,
                    self.id_obfuscator.encode(facility.facility_id),
                ),
            )
            for facility in facility_configs
        ]

        return scheduling_dot_v1_dot_scheduling__pb2.GetAllOrgFacilitiesResponse(
            all_org_facilities=org_facs,
        )

    async def get_monthly_schedule(
        self,
        request: scheduling_pb2.GetMonthlyScheduleRequest,
        ctx: RequestContext[
            scheduling_pb2.GetMonthlyScheduleRequest,
            scheduling_pb2.GetMonthlyScheduleResponse,
        ],
    ) -> scheduling_pb2.GetMonthlyScheduleResponse:
        org_fac_result = self._decode_org_and_facility(
            request.org_id, request.facility_id
        )
        if isinstance(org_fac_result, Failure):
            return scheduling_pb2.GetMonthlyScheduleResponse()
        org_id, facility_id = org_fac_result.unwrap()

        await self._validate_tenant_access(org_id, facility_id)

        with tracer.start_as_current_span("get_monthly_schedule") as span:
            span.set_attribute("org_id", str(org_id))
            span.set_attribute("facility_id", str(facility_id))

            scheduler_container = self._build_scheduler_container()
            async with container_context(
                self._scheduler_context(scheduler_container),
                scope=ContextScopes.REQUEST,
            ):
                scheduler_service: WorkforceSchedulerFacadePort = (
                    await scheduler_container.scheduler_service.resolve()
                )
                (
                    schedule,
                    shifts,
                    employees,
                    facility_config,
                ) = await scheduler_service.get_monthly_schedule(
                    org_id=org_id,
                    facility_id=facility_id,
                    start_date=request.start_date,
                )
                active_run = None
                if schedule.schedule_id is not None and schedule.facility_id is not None:
                    status_result = await scheduler_service.get_schedule_status(
                        org_id=org_id,
                        facility_id=schedule.facility_id,
                        schedule_id=schedule.schedule_id,
                        current_schedule_version=schedule.schedule_version,
                    )
                    status_run = status_result[1]
                    if status_run is not None:
                        active_run = await scheduler_service.get_optimization_run(
                            status_run.run_id
                        )

        day_schedules = map_monthly_schedule(
            obfuscator=self.id_obfuscator,
            schedule=schedule,
            shifts=shifts,
            employees=employees,
            facility_tz=facility_config.tz,
        )

        response = scheduling_pb2.GetMonthlyScheduleResponse(
            facility_id=DEMO_ID_ALIASES.get(
                facility_config.facility_id,
                self.id_obfuscator.encode(facility_config.facility_id),
            ),
            schedule_id=self.id_obfuscator.encode(schedule.schedule_id)
            if schedule.schedule_id is not None
            else "",
            schedule_version=schedule.schedule_version,
            updated_at=schedule.updated_at or "",
            next_page_token="",
            total_days=0,
        )
        if schedule.latest_optimization is not None:
            response.latest_optimization.CopyFrom(
                map_summary(schedule.latest_optimization)
            )
        if schedule.latest_optimization_stats is not None:
            response.latest_optimization_stats.CopyFrom(
                map_stats_from_values(schedule.latest_optimization_stats)
            )
        if schedule.latest_optimization_financials is not None:
            response.latest_optimization_financials.CopyFrom(
                map_financials_from_values(schedule.latest_optimization_financials)
            )
        if active_run is not None:
            response.active_optimization_run.CopyFrom(
                map_run(self.id_obfuscator, active_run)
            )
        end_date = request.end_date or request.start_date
        for day, day_schedule in day_schedules.items():
            if day < request.start_date or day > end_date:
                continue
            response.schedules[day].CopyFrom(day_schedule)

        page_size = request.page_size if request.page_size > 0 else 31
        page_token = request.page_token if request.page_token else None
        if page_token:
            try:
                effective_start = base64.urlsafe_b64decode(
                    page_token.encode()
                ).decode()
            except (ValueError, UnicodeDecodeError):
                effective_start = request.start_date
        else:
            effective_start = request.start_date

        sorted_days = sorted(day for day in response.schedules)
        total_days = len(sorted_days)

        effective_days = [d for d in sorted_days if d >= effective_start]
        visible_days = effective_days[:page_size]
        page_day_set = set(visible_days)

        for day in list(response.schedules.keys()):
            if day not in page_day_set:
                del response.schedules[day]

        next_page_token = ""
        if len(effective_days) > page_size:
            last_visible = visible_days[-1]
            next_date = date.fromisoformat(last_visible) + timedelta(days=1)
            next_page_token = base64.urlsafe_b64encode(
                next_date.isoformat().encode()
            ).decode()

        response.next_page_token = next_page_token
        response.total_days = total_days

        return response

    async def get_schedule_status(
        self,
        request: scheduling_pb2.GetScheduleStatusRequest,
        ctx: RequestContext[
            scheduling_pb2.GetScheduleStatusRequest,
            scheduling_pb2.GetScheduleStatusResponse,
        ],
    ) -> scheduling_pb2.GetScheduleStatusResponse:
        org_fac_result = self._decode_org_and_facility(
            request.org_id, request.facility_id
        )
        if isinstance(org_fac_result, Failure):
            return scheduling_pb2.GetScheduleStatusResponse()
        org_id, facility_id = org_fac_result.unwrap()
        schedule_result = get_internal_id(
            self.id_obfuscator, request.schedule_id, "Schedule"
        )
        if isinstance(schedule_result, Failure):
            return scheduling_pb2.GetScheduleStatusResponse()
        schedule_id = schedule_result.unwrap()
        if schedule_id is None:
            raise DataIntegrityError("Expected non-null value from schedule_id decode")

        await self._validate_tenant_access(org_id, facility_id)

        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
            scope=ContextScopes.REQUEST,
        ):
            scheduler_service: WorkforceSchedulerFacadePort = (
                await scheduler_container.scheduler_service.resolve()
            )
            if facility_id is None:
                return scheduling_pb2.GetScheduleStatusResponse()
            (
                schedule,
                active_run,
                has_newer_version,
            ) = await scheduler_service.get_schedule_status(
                org_id=org_id,
                facility_id=facility_id,
                schedule_id=schedule_id,
                current_schedule_version=request.current_schedule_version,
            )

        response = scheduling_pb2.GetScheduleStatusResponse(
            schedule_id=request.schedule_id,
            latest_schedule_version=schedule.schedule_version,
            has_newer_version=has_newer_version,
            updated_at=schedule.updated_at or "",
        )
        if schedule.latest_optimization is not None:
            response.latest_optimization.CopyFrom(
                map_summary(schedule.latest_optimization)
            )
        if schedule.latest_optimization_stats is not None:
            response.latest_optimization_stats.CopyFrom(
                map_stats_from_values(schedule.latest_optimization_stats)
            )
        if schedule.latest_optimization_financials is not None:
            response.latest_optimization_financials.CopyFrom(
                map_financials_from_values(schedule.latest_optimization_financials)
            )
        if active_run is not None:
            response.active_optimization_run.CopyFrom(
                map_run(self.id_obfuscator, active_run)
            )
        return response

    async def optimize_schedule(
        self,
        request: scheduling_pb2.OptimizeScheduleRequest,
        context: RequestContext[
            scheduling_pb2.OptimizeScheduleRequest,
            scheduling_pb2.OptimizeScheduleResponse,
        ],
    ) -> scheduling_pb2.OptimizeScheduleResponse:
        org_fac_result = self._decode_org_and_facility(
            request.org_id, request.facility_id
        )
        if isinstance(org_fac_result, Failure):
            return scheduling_pb2.OptimizeScheduleResponse(
                is_success=False,
                error_details=org_fac_result.failure(),
            )
        org_id, facility_id = org_fac_result.unwrap()
        if facility_id is None:
            return scheduling_pb2.OptimizeScheduleResponse(
                is_success=False,
                error_details="Facility is required for optimization.",
            )
        await self._validate_tenant_access(org_id, facility_id)
        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
            scope=ContextScopes.REQUEST,
        ):
            scheduler_service: WorkforceSchedulerFacadePort = (
                await scheduler_container.scheduler_service.resolve()
            )
            result = await scheduler_service.optimize_schedule_for_facility(
                OptimizeScheduleRequest(
                    org_id=org_id,
                    facility_id=facility_id,
                    start_date=request.start_date,
                    end_date=request.end_date or request.start_date,
                    settings=map_settings(request.settings),
                    persist_result=request.persist_result,
                )
            )

        return await map_optimize_response(
            self.id_obfuscator, result, self._build_scheduler_container()
        )

    async def start_optimization_run(
        self,
        request: scheduling_pb2.StartOptimizationRunRequest,
        context: RequestContext[
            scheduling_pb2.StartOptimizationRunRequest,
            scheduling_pb2.StartOptimizationRunResponse,
        ],
    ) -> scheduling_pb2.StartOptimizationRunResponse:
        org_fac_result = self._decode_org_and_facility(
            request.org_id, request.facility_id
        )
        if isinstance(org_fac_result, Failure):
            return scheduling_pb2.StartOptimizationRunResponse(
                accepted=False,
                error_details=org_fac_result.failure(),
            )
        org_id, facility_id = org_fac_result.unwrap()
        if facility_id is None:
            return scheduling_pb2.StartOptimizationRunResponse(
                accepted=False,
                error_details="Facility is required for optimization.",
            )
        await self._validate_tenant_access(org_id, facility_id)
        schedule_result = get_internal_id(
            self.id_obfuscator, request.schedule_id, "Schedule"
        )
        if isinstance(schedule_result, Failure):
            return scheduling_pb2.StartOptimizationRunResponse(
                accepted=False,
                error_details=schedule_result.failure(),
            )
        schedule_id = schedule_result.unwrap()
        if schedule_id is None:
            raise DataIntegrityError("Expected non-null value from schedule_id decode")

        patches_result = decode_staged_patches(
            self.id_obfuscator, list(request.staged_patches)
        )
        if isinstance(patches_result, Failure):
            return scheduling_pb2.StartOptimizationRunResponse(
                accepted=False,
                error_details=patches_result.failure(),
            )

        with tracer.start_as_current_span("start_optimization_run") as span:
            span.set_attribute("org_id", str(org_id))
            span.set_attribute("facility_id", str(facility_id))
            span.set_attribute("client_request_id", request.client_request_id or "")
            # Idempotency: client_request_id dedup is enforced in
            # scheduler_facade.start_optimization_run.
            # Future: use persistence/idempotency_repo.IdempotencyStore
            # to cache and replay response payloads.

            scheduler_container = self._build_scheduler_container()
            async with container_context(
                self._scheduler_context(scheduler_container),
                scope=ContextScopes.REQUEST,
            ):
                scheduler_service: WorkforceSchedulerFacadePort = (
                    await scheduler_container.scheduler_service.resolve()
                )
                result = await scheduler_service.start_optimization_run(
                    StartOptimizationRunRequest(
                        org_id=org_id,
                        facility_id=facility_id,
                        schedule_id=schedule_id,
                        base_schedule_version=request.base_schedule_version,
                        start_date=request.start_date,
                        end_date=request.end_date or request.start_date,
                        settings=map_settings(request.settings),
                        staged_patches=patches_result.unwrap(),
                        persist_result=request.persist_result,
                        client_request_id=request.client_request_id or None,
                        allow_overwrite=request.allow_overwrite,
                    )
                )

        response = scheduling_pb2.StartOptimizationRunResponse(
            accepted=result.is_success,
            error_details=result.error_details or "",
            version_conflict=result.validation_level == "stale",
            latest_schedule_version=result.latest_schedule_version or 0,
        )
        if result.run is not None:
            response.run.CopyFrom(map_run(self.id_obfuscator, result.run))
        for conflict in result.conflicts:
            response.conflicts.append(map_conflict(self.id_obfuscator, conflict))
        return response

    async def get_optimization_run(
        self,
        request: scheduling_pb2.GetOptimizationRunRequest,
        context: RequestContext[
            scheduling_pb2.GetOptimizationRunRequest,
            scheduling_pb2.GetOptimizationRunResponse,
        ],
    ) -> scheduling_pb2.GetOptimizationRunResponse:
        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
            scope=ContextScopes.REQUEST,
        ):
            scheduler_service: WorkforceSchedulerFacadePort = (
                await scheduler_container.scheduler_service.resolve()
            )
            run = await scheduler_service.get_optimization_run(request.run_id)

        response = scheduling_pb2.GetOptimizationRunResponse(found=run is not None)
        if run is None:
            return response
        response.run.CopyFrom(map_run(self.id_obfuscator, run))
        if run.result_schedule_id is None:
            return response

        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
            scope=ContextScopes.REQUEST,
        ):
            scheduler_service = await scheduler_container.scheduler_service.resolve()
            (
                schedule,
                shifts,
                employees,
                facility_config,
            ) = await scheduler_service.get_monthly_schedule(
                org_id=run.org_id,
                facility_id=run.facility_id,
                start_date=run.started_at[:10]
                if run.started_at
                else whenever.Instant.now().format_iso()[:10],
            )
        for day, day_schedule in map_monthly_schedule(
            obfuscator=self.id_obfuscator,
            schedule=schedule,
            shifts=shifts,
            employees=employees,
            facility_tz=facility_config.tz,
        ).items():
            response.schedules[day].CopyFrom(day_schedule)
        return response

    async def stream_optimization_run(
        self,
        request: scheduling_pb2.StreamOptimizationRunRequest,
        context: RequestContext[
            scheduling_pb2.StreamOptimizationRunRequest,
            scheduling_pb2.OptimizationRunEvent,
        ],
    ) -> AsyncIterator[scheduling_pb2.OptimizationRunEvent]:
        yielded_sequences: set[int] = set()
        while True:
            scheduler_container = self._build_scheduler_container()
            async with container_context(
                self._scheduler_context(scheduler_container),
                scope=ContextScopes.REQUEST,
            ):
                scheduler_service: WorkforceSchedulerFacadePort = (
                    await scheduler_container.scheduler_service.resolve()
                )
                run = await scheduler_service.get_optimization_run(request.run_id)
                schedule_repo = await scheduler_container.schedule_retriever.resolve()
                events = await schedule_repo.list_optimization_run_events(
                    request.run_id
                )

            if run is None:
                break

            latest_response = await self.get_optimization_run(
                scheduling_pb2.GetOptimizationRunRequest(run_id=request.run_id),
                cast(
                    RequestContext[
                        scheduling_pb2.GetOptimizationRunRequest,
                        scheduling_pb2.GetOptimizationRunResponse,
                    ],
                    context,
                ),
            )

            for event in events:
                if event.sequence in yielded_sequences:
                    continue
                yielded_sequences.add(event.sequence)
                event_run = (
                    run
                    if event.sequence == events[-1].sequence
                    else OptimizationRun(
                        **{
                            **run.__dict__,
                            "status": event.status,
                            "stage": event.stage,
                            "progress_percent": event.progress_percent,
                            "status_message": event.status_message,
                            "error_details": event.error_details,
                        }
                    )
                )
                yield scheduling_pb2.OptimizationRunEvent(
                    sequence=event.sequence,
                    run=map_run(self.id_obfuscator, event_run),
                    schedules=latest_response.schedules
                    if event.sequence == events[-1].sequence
                    else {},
                )

            if latest_response.run.status in {
                scheduling_pb2.OPTIMIZATION_RUN_STATUS_COMPLETED,
                scheduling_pb2.OPTIMIZATION_RUN_STATUS_FAILED,
            }:
                break
            await asyncio.sleep(1)

    async def validate_shift_move(
        self,
        request: scheduling_pb2.ValidateShiftMoveRequest,
        context: RequestContext[
            scheduling_pb2.ValidateShiftMoveRequest,
            scheduling_pb2.ValidateShiftMoveResponse,
        ],
    ) -> scheduling_pb2.ValidateShiftMoveResponse:
        res = await self._validate_shift_move(request)
        if isinstance(res, Failure):
            return scheduling_pb2.ValidateShiftMoveResponse(
                is_success=False,
                is_valid=False,
                error_details=res.failure(),
            )
        return res.unwrap()

    async def _validate_shift_move(
        self,
        request: scheduling_pb2.ValidateShiftMoveRequest,
    ) -> Result[scheduling_pb2.ValidateShiftMoveResponse, str]:
        obfuscator = self.id_obfuscator

        def _required_id(val: str, label: str) -> Result[int, str]:
            result = get_internal_id(obfuscator, val, label)
            if isinstance(result, Failure):
                return Failure(result.failure())
            internal = result.unwrap()
            if internal is None:
                raise DataIntegrityError(f"Expected non-null value from {label} ID decode")
            return Success(internal)

        def _optional_id(val: str, label: str) -> Result[int | None, str]:
            return get_internal_id(obfuscator, val, label, required=False)

        employee_result = _required_id(request.employee_id, "Employee")
        if isinstance(employee_result, Failure):
            return Failure(employee_result.failure())
        employee_id = employee_result.unwrap()
        from_result = _optional_id(request.from_shift_id, "Shift")
        if isinstance(from_result, Failure):
            return Failure(from_result.failure())
        from_shift_id = from_result.unwrap()
        to_result = _optional_id(request.to_shift_id, "Shift")
        if isinstance(to_result, Failure):
            return Failure(to_result.failure())
        to_shift_id = to_result.unwrap()
        sched_result = _required_id(request.schedule_id, "Schedule")
        if isinstance(sched_result, Failure):
            return Failure(sched_result.failure())
        schedule_id = sched_result.unwrap()
        org_result = _required_id(request.org_id, "Organization")
        if isinstance(org_result, Failure):
            return Failure(org_result.failure())
        org_id = org_result.unwrap()
        fac_result = _required_id(request.facility_id, "Facility")
        if isinstance(fac_result, Failure):
            return Failure(fac_result.failure())
        facility_id = fac_result.unwrap()

        await self._validate_tenant_access(org_id, facility_id)

        patches_result = decode_staged_patches(
            self.id_obfuscator, list(request.staged_patches)
        )
        if isinstance(patches_result, Failure):
            return Failure(patches_result.failure())

        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
            scope=ContextScopes.REQUEST,
        ):
            scheduler_service: WorkforceSchedulerFacadePort = (
                await scheduler_container.scheduler_service.resolve()
            )
            result = await scheduler_service.validate_shift_move(
                move_request=MoveEmployeeRequest(
                    org_id=org_id,
                    facility_id=facility_id,
                    schedule_id=schedule_id,
                    employee_id=employee_id,
                    from_shift_id=from_shift_id,
                    to_shift_id=to_shift_id,
                    schedule_version=request.schedule_version,
                    staged_patches=patches_result.unwrap(),
                    patch_id=request.patch_id or None,
                ),
                pay_period_start=whenever.Instant.from_timestamp(
                    request.pay_period_start_ts
                ),
            )

        return Success(
            await map_validation_response(
                self.id_obfuscator,
                result,
                self._build_scheduler_container(),
            )
        )

    async def remove_nurse_from_shift(
        self,
        request: scheduling_pb2.RemoveNurseFromShiftRequest,
        context: RequestContext[
            scheduling_pb2.RemoveNurseFromShiftRequest,
            scheduling_pb2.RemoveNurseFromShiftResponse,
        ],
    ) -> scheduling_pb2.RemoveNurseFromShiftResponse:
        return scheduling_pb2.RemoveNurseFromShiftResponse(
            success=False,
            message="RemoveNurseFromShift is not implemented in the run-based flow.",
        )

    def _decode_org_and_facility(
        self, org_id: str, facility_id: str
    ) -> Result[tuple[int, int | None], str]:
        org_result = get_internal_id(self.id_obfuscator, org_id, "Organization")
        if isinstance(org_result, Failure):
            return Failure(org_result.failure())
        internal_org_id = org_result.unwrap()
        if internal_org_id is None:
            raise DataIntegrityError("Expected non-null value from org_id decode")

        facility_result = get_internal_id(
            self.id_obfuscator,
            facility_id,
            "Facility",
            required=False,
        )
        if isinstance(facility_result, Failure):
            return Failure(facility_result.failure())
        return Success((internal_org_id, facility_result.unwrap()))

    @staticmethod
    def _unwrap_required_id(result: Result[int | None, str]) -> int:
        if isinstance(result, Failure):
            raise ValueError(result.failure())
        value = result.unwrap()
        if value is None:
            raise DataIntegrityError("Expected non-null value from unwrap_required_id")
        return value

    @staticmethod
    def _unwrap_optional_id(result: Result[int | None, str]) -> int | None:
        if isinstance(result, Failure):
            raise ValueError(result.failure())
        return result.unwrap()
