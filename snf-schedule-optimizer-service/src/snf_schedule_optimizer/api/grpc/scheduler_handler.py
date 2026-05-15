import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping
from typing import Any, cast

import whenever
from connectrpc.request import RequestContext
from returns.result import Failure, Result, Success, safe
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from that_depends import container_context
from that_depends.providers.context_resources import ContextScopes, SupportsContext

from snf_schedule_optimizer.api import (
    MoveEmployeeRequest,
    OptimizationOutput,
    OptimizeScheduleRequest,
    StartOptimizationRunRequest,
)
from snf_schedule_optimizer.domain.exceptions import SecurityError
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
from snf_schedule_optimizer.service.facility.facility_facade import FacilityFacade
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacadePort,
)

logger = logging.getLogger(__name__)


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
    ):
        self.engine = engine
        self.session_factory = session_factory
        self.id_obfuscator = id_obfuscator
        self._repos_container = build_repos_container(self.engine, self.session_factory)
        self._scheduler_container = build_scheduler_container(self._repos_container)
        self._facility_container = build_facility_container(self._repos_container)

    def _build_scheduler_container(self) -> type[ISchedulerContainer]:
        return self._scheduler_container

    def _build_facility_container(self) -> type[IFacilityContainer]:
        return self._facility_container

    def _scheduler_context(
        self, scheduler_container: type[ISchedulerContainer]
    ) -> SupportsContext[Any]:
        return cast(SupportsContext[Any], scheduler_container)

    def _facility_context(
        self, facility_container: type[IFacilityContainer]
    ) -> SupportsContext[Any]:
        return cast(SupportsContext[Any], facility_container)

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

        day_schedules = self._map_monthly_schedule(
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
        )
        if schedule.latest_optimization is not None:
            response.latest_optimization.CopyFrom(
                self._map_summary(schedule.latest_optimization)
            )
        if schedule.latest_optimization_stats is not None:
            response.latest_optimization_stats.CopyFrom(
                self._map_stats_from_values(schedule.latest_optimization_stats)
            )
        if schedule.latest_optimization_financials is not None:
            response.latest_optimization_financials.CopyFrom(
                self._map_financials_from_values(
                    schedule.latest_optimization_financials
                )
            )
        if active_run is not None:
            response.active_optimization_run.CopyFrom(self._map_run(active_run))
        end_date = request.end_date or request.start_date
        for day, day_schedule in day_schedules.items():
            if day < request.start_date or day > end_date:
                continue
            response.schedules[day].CopyFrom(day_schedule)
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
        assert schedule_id is not None

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
                self._map_summary(schedule.latest_optimization)
            )
        if schedule.latest_optimization_stats is not None:
            response.latest_optimization_stats.CopyFrom(
                self._map_stats_from_values(schedule.latest_optimization_stats)
            )
        if schedule.latest_optimization_financials is not None:
            response.latest_optimization_financials.CopyFrom(
                self._map_financials_from_values(
                    schedule.latest_optimization_financials
                )
            )
        if active_run is not None:
            response.active_optimization_run.CopyFrom(self._map_run(active_run))
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
                    settings=self._map_settings(request.settings),
                    persist_result=request.persist_result,
                )
            )

        return await self._map_optimize_response(result)

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
        assert schedule_id is not None

        patches_result = self._decode_staged_patches(list(request.staged_patches))
        if isinstance(patches_result, Failure):
            return scheduling_pb2.StartOptimizationRunResponse(
                accepted=False,
                error_details=patches_result.failure(),
            )

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
                    settings=self._map_settings(request.settings),
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
            response.run.CopyFrom(self._map_run(result.run))
        for conflict in result.conflicts:
            response.conflicts.append(self._map_conflict(conflict))
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
        response.run.CopyFrom(self._map_run(run))
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
        for day, day_schedule in self._map_monthly_schedule(
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
                    run=self._map_run(event_run),
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
            assert internal is not None
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

        patches_result = self._decode_staged_patches(list(request.staged_patches))
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

        return Success(await self._map_validation_response(result))

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

    async def _map_validation_response(
        self,
        result: OptimizationOutput,
    ) -> scheduling_pb2.ValidateShiftMoveResponse:
        response = scheduling_pb2.ValidateShiftMoveResponse(
            is_success=result.is_success,
            is_valid=result.is_valid,
            validation_level=self._map_validation_level(result.validation_level),
            error_details=result.error_details or "",
            total_cost=result.financials.total_enterprise_cost
            if result.financials
            else 0.0,
            latest_schedule_version=result.latest_schedule_version or 0,
            is_stale=result.validation_level == "stale",
        )
        if result.financials is not None:
            response.financials.CopyFrom(
                self._map_financials_from_values(result.financials)
            )
        if result.stats is not None:
            response.stats.CopyFrom(self._map_stats_from_values(result.stats))
        for warning in result.warnings:
            response.warnings.append(warning)
        for conflict in result.conflicts:
            response.conflicts.append(self._map_conflict(conflict))
        if result.patches:
            response.patch.CopyFrom(self._map_patch(result.patches[-1]))
        if result.schedule is not None:
            try:
                (
                    schedule,
                    shifts,
                    employees,
                    facility_config,
                ) = await self._load_schedule_dependencies(
                    result.schedule.org_id,
                    result.schedule,
                )
                for day, day_schedule in self._map_monthly_schedule(
                    schedule=schedule,
                    shifts=shifts,
                    employees=employees,
                    facility_tz=facility_config.tz,
                ).items():
                    response.affected_schedules[day].CopyFrom(day_schedule)
            except Exception:
                logger.warning(
                    "Failed to load schedule dependencies for validation response org_id=%s",
                    result.schedule.org_id,
                    exc_info=True,
                )
        return response

    async def _map_optimize_response(
        self,
        result: OptimizationOutput,
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
        ) = await self._load_schedule_dependencies(
            result.schedule.org_id,
            result.schedule,
        )
        for day, day_schedule in self._map_monthly_schedule(
            schedule=schedule,
            shifts=shifts,
            employees=employees,
            facility_tz=facility_config.tz,
        ).items():
            response.schedules[day].CopyFrom(day_schedule)
        response.facility_id = DEMO_ID_ALIASES.get(
            facility_config.facility_id,
            self.id_obfuscator.encode(facility_config.facility_id),
        )
        if result.schedule.schedule_id is None:
            raise ValueError("Optimized schedule is missing schedule_id")
        response.schedule_id = self.id_obfuscator.encode(result.schedule.schedule_id)
        response.schedule_version = result.schedule.schedule_version
        if result.financials is not None:
            response.financials.CopyFrom(
                self._map_financials_from_values(result.financials)
            )
        if result.stats is not None:
            response.stats.CopyFrom(self._map_stats_from_values(result.stats))
        if result.summary is not None:
            response.summary.CopyFrom(self._map_summary(result.summary))
        return response

    def _map_financials_from_values(
        self,
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

    def _map_stats_from_values(self, stats: Any) -> scheduling_pb2.OptimizationStats:
        return scheduling_pb2.OptimizationStats(
            execution_time_ms=stats.execution_time_ms,
            objective_value=stats.objective_value or 0.0,
            total_variables=stats.total_variables,
            total_constraints=stats.total_constraints,
        )

    def _map_summary(
        self,
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
                overtime_avoidance_penalty=summary.applied_settings.overtime_avoidance_penalty,
                team_consistency_penalty=summary.applied_settings.team_consistency_penalty,
                high_risk_shift_penalty=summary.applied_settings.high_risk_shift_penalty,
                custom_preference_penalty=summary.applied_settings.custom_preference_penalty,
            ),
        )

    def _map_settings(
        self,
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

    async def _load_schedule_dependencies(
        self,
        org_id: int,
        schedule: Schedule,
    ) -> tuple[
        Schedule, Mapping[ShiftKey, Shift], Mapping[int, Employee], FacilityConfig
    ]:
        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
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

    def _map_monthly_schedule(
        self,
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
            shift_date = (
                shift.shift_start_dt.to_tz(facility_tz).date().format_common_iso()
            )
            nurse_messages = []
            for employee_id in employee_ids:
                employee = employees.get(employee_id)
                if employee is None:
                    continue
                nurse_messages.append(
                    scheduling_pb2.Nurse(
                        id=self.id_obfuscator.encode(employee_id),
                        name=employee.name,
                        shift_hours=shift.duration_hours,
                        scheduling_rationale="Seeded demo assignment",
                        role=employee.job_title,
                        is_agency=False,
                    )
                )

            actual_hours = sum(nurse.shift_hours for nurse in nurse_messages)
            target_hrpd = self._target_hrpd(shift)
            patient_census = self._patient_census(shift)
            actual_hrpd = actual_hours / patient_census if patient_census else 0.0
            grouped[shift_date].append(
                scheduling_pb2.Shift(
                    shift_id=self.id_obfuscator.encode(shift.shift_id),
                    shift_name=self._shift_name(shift.shift_number),
                    patient_census=patient_census,
                    target_hrpd=target_hrpd,
                    actual_hrpd=actual_hrpd,
                    is_hrpd_met=actual_hrpd >= target_hrpd,
                    nurses=nurse_messages,
                    unit_id=self._unit_key(shift.unit_id),
                    unit_name=self._unit_name(shift.unit_id),
                )
            )

        return {
            day: scheduling_pb2.DaySchedule(date=day, shifts=day_shifts)
            for day, day_shifts in grouped.items()
        }

    def _map_patch(
        self, patch: StagedSchedulePatch
    ) -> scheduling_pb2.StagedSchedulePatch:
        return scheduling_pb2.StagedSchedulePatch(
            patch_id=patch.patch_id,
            employee_id=self.id_obfuscator.encode(patch.employee_id),
            employee_name=patch.employee_name or "",
            from_shift_id=self.id_obfuscator.encode(patch.from_shift_id)
            if patch.from_shift_id is not None
            else "",
            to_shift_id=self.id_obfuscator.encode(patch.to_shift_id)
            if patch.to_shift_id is not None
            else "",
            pinned=patch.pinned,
            warnings=list(patch.warnings),
            validation_level=self._map_validation_level(patch.validation_level),
            causes_overtime=patch.causes_overtime,
            total_cost=patch.total_cost,
            created_at=patch.created_at or "",
        )

    def _decode_patch(
        self, patch: scheduling_pb2.StagedSchedulePatch
    ) -> Result[StagedSchedulePatch, str]:
        employee_id_result = get_internal_id(
            self.id_obfuscator, patch.employee_id, "Employee"
        )
        if isinstance(employee_id_result, Failure):
            return Failure(employee_id_result.failure())
        employee_id = employee_id_result.unwrap()
        assert employee_id is not None
        from_shift_id_result = get_internal_id(
            self.id_obfuscator, patch.from_shift_id, "Shift", required=False
        )
        if isinstance(from_shift_id_result, Failure):
            return Failure(from_shift_id_result.failure())
        from_shift_id = from_shift_id_result.unwrap()
        to_shift_id_result = get_internal_id(
            self.id_obfuscator, patch.to_shift_id, "Shift", required=False
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
                validation_level=self._validation_level_name(patch.validation_level),
                causes_overtime=patch.causes_overtime,
                total_cost=patch.total_cost,
                created_at=patch.created_at or None,
            )
        )

    def _decode_staged_patches(
        self,
        patches: list[scheduling_pb2.StagedSchedulePatch],
    ) -> Result[tuple[StagedSchedulePatch, ...], str]:
        decoded: list[StagedSchedulePatch] = []
        for patch in patches:
            result = self._decode_patch(patch)
            if isinstance(result, Failure):
                return Failure(result.failure())
            decoded.append(result.unwrap())
        return Success(tuple(decoded))

    def _map_conflict(self, conflict: PatchConflict) -> scheduling_pb2.PatchConflict:
        return scheduling_pb2.PatchConflict(
            patch_id=conflict.patch_id,
            employee_id=self.id_obfuscator.encode(conflict.employee_id),
            employee_name=conflict.employee_name or "",
            from_shift_id=self.id_obfuscator.encode(conflict.from_shift_id)
            if conflict.from_shift_id is not None
            else "",
            to_shift_id=self.id_obfuscator.encode(conflict.to_shift_id)
            if conflict.to_shift_id is not None
            else "",
            reason=conflict.reason,
            latest_shift_id=self.id_obfuscator.encode(conflict.latest_shift_id)
            if conflict.latest_shift_id is not None
            else "",
        )

    def _map_run(self, run: OptimizationRun) -> scheduling_pb2.OptimizationRun:
        proto_run = scheduling_pb2.OptimizationRun(
            run_id=run.run_id,
            schedule_id=self.id_obfuscator.encode(run.schedule_id),
            base_schedule_version=run.base_schedule_version,
            result_schedule_version=run.result_schedule_version or 0,
            status=self._map_run_status(run.status),
            stage=self._map_run_stage(run.stage),
            progress_percent=run.progress_percent,
            status_message=run.status_message,
            started_at=run.started_at or "",
            completed_at=run.completed_at or "",
            error_details=run.error_details or "",
        )
        if run.financials is not None:
            proto_run.financials.CopyFrom(
                self._map_financials_from_values(run.financials)
            )
        if run.stats is not None:
            proto_run.stats.CopyFrom(self._map_stats_from_values(run.stats))
        if run.summary is not None:
            proto_run.summary.CopyFrom(self._map_summary(run.summary))
        return proto_run

    def _decode_org_and_facility(
        self, org_id: str, facility_id: str
    ) -> Result[tuple[int, int | None], str]:
        org_result = get_internal_id(self.id_obfuscator, org_id, "Organization")
        if isinstance(org_result, Failure):
            return Failure(org_result.failure())
        internal_org_id = org_result.unwrap()
        assert internal_org_id is not None

        facility_result = get_internal_id(
            self.id_obfuscator,
            facility_id,
            "Facility",
            required=False,
        )
        if isinstance(facility_result, Failure):
            return Failure(facility_result.failure())
        return Success((internal_org_id, facility_result.unwrap()))

    async def _validate_tenant_access(
        self, org_id: int, facility_id: int | None = None
    ) -> None:
        facility_container = self._build_facility_container()
        async with container_context(
            self._facility_context(facility_container),
            scope=ContextScopes.REQUEST,
        ):
            facility_facade: FacilityFacade = (
                await facility_container.facility_facade.resolve()
            )
            if facility_id is not None:
                config = await facility_facade.get_facility_config(org_id, facility_id)
                if config is None:
                    raise SecurityError(
                        f"Facility {facility_id} does not belong to organization {org_id}."
                    )
            else:
                org_facilities = await facility_facade.get_all_org_facilities(org_id)
                if not org_facilities:
                    raise SecurityError(
                        f"Organization {org_id} not found or access denied."
                    )

    @staticmethod
    def _unwrap_required_id(result: Result[int | None, str]) -> int:
        if isinstance(result, Failure):
            raise ValueError(result.failure())
        value = result.unwrap()
        assert value is not None
        return value

    @staticmethod
    def _unwrap_optional_id(result: Result[int | None, str]) -> int | None:
        if isinstance(result, Failure):
            raise ValueError(result.failure())
        return result.unwrap()

    @staticmethod
    def _map_validation_level(level: str) -> str:
        return {
            "ok": "VALIDATION_OK",
            "warning": "VALIDATION_WARNING",
            "critical": "VALIDATION_CRITICAL",
            "stale": "VALIDATION_STALE",
            "unspecified": "VALIDATION_LEVEL_UNSPECIFIED",
        }.get(level, "VALIDATION_LEVEL_UNSPECIFIED")

    @staticmethod
    def _validation_level_name(level: int) -> str:
        normalized_level = int(level)
        mapping = {
            int(scheduling_pb2.VALIDATION_OK): "ok",
            int(scheduling_pb2.VALIDATION_WARNING): "warning",
            int(scheduling_pb2.VALIDATION_CRITICAL): "critical",
            int(scheduling_pb2.VALIDATION_STALE): "stale",
        }
        return mapping.get(normalized_level, "unspecified")

    @staticmethod
    def _map_run_status(status: str) -> str:
        return {
            "queued": "OPTIMIZATION_RUN_STATUS_QUEUED",
            "running": "OPTIMIZATION_RUN_STATUS_RUNNING",
            "completed": "OPTIMIZATION_RUN_STATUS_COMPLETED",
            "failed": "OPTIMIZATION_RUN_STATUS_FAILED",
        }.get(status, "OPTIMIZATION_RUN_STATUS_UNSPECIFIED")

    @staticmethod
    def _map_run_stage(stage: str) -> str:
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

    def _shift_name(self, shift_number: int) -> str:
        return {1: "Morning", 2: "Afternoon", 3: "Night"}.get(
            shift_number,
            f"Shift {shift_number}",
        )

    @staticmethod
    def _unit_key(unit_id: int | None) -> str:
        return f"unit-{unit_id}" if unit_id is not None else "unit-unknown"

    def _unit_name(self, unit_id: int | None) -> str:
        return {
            101: "Short-Term Rehab",
            102: "Long-Term Care",
            103: "Memory Care",
            104: "Skilled/Subacute",
        }.get(unit_id or 0, "Unassigned Unit")

    def _patient_census(self, shift: Shift) -> int:
        base_by_unit = {101: 34, 102: 48, 103: 32, 104: 24}
        census = base_by_unit.get(shift.unit_id or 0, 36)
        if shift.shift_number == 3:
            census -= 2
        if shift.day_of_week in {whenever.Weekday(1), whenever.Weekday(5)}:
            census += 2
        if self._is_weekend(shift):
            census -= 1
        return max(census, 18)

    def _target_hrpd(self, shift: Shift) -> float:
        target_by_unit = {101: 3.9, 102: 3.55, 103: 3.7, 104: 4.15}
        target = target_by_unit.get(shift.unit_id or 0, 3.65)
        if shift.shift_number == 3:
            target -= 0.25
        if self._is_weekend(shift):
            target += 0.10
        return round(target, 2)

    @staticmethod
    def _is_weekend(shift: Shift) -> bool:
        return shift.day_of_week in {whenever.Weekday(6), whenever.Weekday(7)}
