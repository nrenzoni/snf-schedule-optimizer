from collections import defaultdict
from collections.abc import Mapping
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
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    OptimizationSettings,
    OptimizationSummary,
    Schedule,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.service.facility.facility_facade import FacilityFacade
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacadePort,
)


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
            facility_facade: FacilityFacade = await facility_container.facility_facade.resolve()
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
        org_result = get_internal_id(self.id_obfuscator, request.org_id, "Organization")
        if isinstance(org_result, Failure):
            raise ValueError(org_result.failure())
        org_id = org_result.unwrap()
        assert org_id is not None

        facility_result = get_internal_id(
            self.id_obfuscator,
            request.facility_id,
            "Facility",
            required=False,
        )
        if isinstance(facility_result, Failure):
            raise ValueError(facility_result.failure())
        facility_id = facility_result.unwrap()

        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
            scope=ContextScopes.REQUEST,
        ):
            scheduler_service: WorkforceSchedulerFacadePort = (
                await scheduler_container.scheduler_service.resolve()
            )
            schedule, shifts, employees, facility_config = (
                await scheduler_service.get_monthly_schedule(
                    org_id=org_id,
                    facility_id=facility_id,
                    start_date=request.start_date,
                )
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
        )
        if schedule.latest_optimization is not None:
            response.latest_optimization.CopyFrom(
                self._map_summary(schedule.latest_optimization)
            )
        end_date = request.end_date or request.start_date
        for day, day_schedule in day_schedules.items():
            if day < request.start_date or day > end_date:
                continue
            response.schedules[day].CopyFrom(day_schedule)
        return response

    async def optimize_schedule(
        self,
        request: scheduling_pb2.OptimizeScheduleRequest,
        context: RequestContext[
            scheduling_pb2.OptimizeScheduleRequest,
            scheduling_pb2.OptimizeScheduleResponse,
        ],
    ) -> scheduling_pb2.OptimizeScheduleResponse:
        org_result = get_internal_id(self.id_obfuscator, request.org_id, "Organization")
        if isinstance(org_result, Failure):
            return scheduling_pb2.OptimizeScheduleResponse(
                is_success=False,
                error_details=org_result.failure(),
            )
        facility_result = get_internal_id(self.id_obfuscator, request.facility_id, "Facility")
        if isinstance(facility_result, Failure):
            return scheduling_pb2.OptimizeScheduleResponse(
                is_success=False,
                error_details=facility_result.failure(),
            )
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
                    org_id=org_result.unwrap() or 0,
                    facility_id=facility_result.unwrap() or 0,
                    start_date=request.start_date,
                    end_date=request.end_date or request.start_date,
                    settings=self._map_settings(request.settings),
                    persist_result=request.persist_result,
                )
            )

        response = scheduling_pb2.OptimizeScheduleResponse(
            is_success=result.is_success,
            error_details=result.error_details or "",
        )
        if result.schedule is not None:
            schedule, shifts, employees, facility_config = await self._load_schedule_dependencies(
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
        if result.financials:
            response.financials.CopyFrom(self._map_financials(result))
        if result.stats:
            response.stats.CopyFrom(self._map_stats(result))
        if result.summary:
            response.summary.CopyFrom(self._map_summary(result.summary))
        return response

    async def validate_shift_move(
        self,
        request: scheduling_pb2.ValidateShiftMoveRequest,
        context: RequestContext[
            scheduling_pb2.ValidateShiftMoveRequest,
            scheduling_pb2.ValidateShiftMoveResponse,
        ],
    ) -> scheduling_pb2.ValidateShiftMoveResponse:
        """
        ConnectRPC implementation that delegates to the WorkforceSchedulerService.
        """
        res = await self._validate_shift_move(request)
        if isinstance(res, Failure):
            return scheduling_pb2.ValidateShiftMoveResponse(
                is_success=False,
                error_details=res.failure(),
            )
        return res.unwrap()

    async def _validate_shift_move(
        self,
        request: scheduling_pb2.ValidateShiftMoveRequest,
    ) -> Result[scheduling_pb2.ValidateShiftMoveResponse, str]:
        obfuscator = self.id_obfuscator

        res = get_internal_id(obfuscator, request.employee_id, "Employee")
        if isinstance(res, Failure):
            return res
        employee_id = res.unwrap()
        assert employee_id is not None

        # from_shift (optional)
        res = get_internal_id(
            obfuscator, request.from_shift_id, "Shift", required=False
        )
        if isinstance(res, Failure):
            return res
        from_shift_id = res.unwrap()

        # to_shift (optional)
        res = get_internal_id(obfuscator, request.to_shift_id, "Shift", required=False)
        if isinstance(res, Failure):
            return res
        to_shift_id = res.unwrap()

        # schedule (required)
        res = get_internal_id(obfuscator, request.schedule_id, "Schedule")
        if isinstance(res, Failure):
            return res
        schedule_id = res.unwrap()
        assert schedule_id is not None

        # org (required)
        res = get_internal_id(obfuscator, request.org_id, "Organization")
        if isinstance(res, Failure):
            return res
        org_id = res.unwrap()
        assert org_id is not None

        # facility (required)
        res = get_internal_id(obfuscator, request.facility_id, "Facility")
        if isinstance(res, Failure):
            return res
        facility_id = res.unwrap()
        assert facility_id is not None

        # 1. Map Proto Request -> Domain DTO
        domain_request = MoveEmployeeRequest(
            org_id=org_id,
            facility_id=facility_id,
            schedule_id=schedule_id,
            employee_id=employee_id,
            from_shift_id=from_shift_id,
            to_shift_id=to_shift_id,
            schedule_version=request.schedule_version,
        )

        # 2. Call Application Layer (Facade)
        # We pass absolute Instant for cross-facility coordination
        scheduler_container = self._build_scheduler_container()
        async with container_context(
            self._scheduler_context(scheduler_container),
            scope=ContextScopes.REQUEST,
        ):
            scheduler_service: WorkforceSchedulerFacadePort = (
                await scheduler_container.scheduler_service.resolve()
            )
            result: OptimizationOutput = await scheduler_service.validate_shift_move(
                move_request=domain_request,
                pay_period_start=whenever.Instant.from_timestamp(
                    request.pay_period_start_ts
                ),
            )

        # 3. Map Domain Result -> Proto Response
        return self._map_to_response(result)

    def _map_to_response(
        self,
        result: OptimizationOutput,
    ) -> scheduling_pb2.ValidateShiftMoveResponse:
        """
        Helper to transform the rich Domain result into a flat Protobuf message.
        """
        response = scheduling_pb2.ValidateShiftMoveResponse(
            is_success=result.is_success,
            error_details=result.error_details or "",
            total_cost=result.financials.total_enterprise_cost
            if result.financials
            else 0.0,
        )

        # Map Financials
        if result.financials:
            # Note: We sum across the enterprise for this specific response
            response.financials.CopyFrom(self._map_financials(result))

        # Map Statistics
        if result.stats:
            response.stats.CopyFrom(self._map_stats(result))

        # Map Updated Schedule (Visual feedback for the UI)
        if result.schedule and result.analysis:
            response.updated_schedule.CopyFrom(self._map_to_day_schedule(result))

        return response

    def _map_financials(
        self,
        result: OptimizationOutput,
    ) -> scheduling_pb2.FinancialReport:
        assert result.financials is not None
        return scheduling_pb2.FinancialReport(
            total_enterprise_cost=result.financials.total_enterprise_cost,
            total_incentive_cost=sum(
                f.bonuses for f in result.financials.breakdown_per_facility.values()
            ),
            total_overtime_cost=sum(
                f.overtime_cost for f in result.financials.breakdown_per_facility.values()
            ),
            regular_pay_cost=sum(
                f.regular_cost for f in result.financials.breakdown_per_facility.values()
            ),
        )

    def _map_stats(
        self,
        result: OptimizationOutput,
    ) -> scheduling_pb2.OptimizationStats:
        assert result.stats is not None
        return scheduling_pb2.OptimizationStats(
            execution_time_ms=result.stats.execution_time_ms,
            objective_value=result.stats.objective_value or 0.0,
            total_variables=result.stats.total_variables,
            total_constraints=result.stats.total_constraints,
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
    ) -> tuple[Schedule, Mapping[ShiftKey, Shift], Mapping[int, Employee], FacilityConfig]:
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

    def _map_to_day_schedule(
        self,
        result: OptimizationOutput,
    ) -> scheduling_pb2.DaySchedule:
        """
        Maps the analyzed schedule into the tree-like Proto structure.
        """
        # We use the analysis report because it contains the hydrated names and roles
        # which the raw Schedule (IDs only) does not.

        if result.analysis is None:
            return scheduling_pb2.DaySchedule()

        proto_shifts = {}

        for assignment in result.analysis.assignments:
            if assignment.shift_id not in proto_shifts:
                proto_shifts[assignment.shift_id] = scheduling_pb2.Shift(
                    shift_id=self.id_obfuscator.encode(assignment.shift_id),
                    # We can use the date from the first assignment found
                )

            proto_shifts[assignment.shift_id].nurses.append(
                scheduling_pb2.Nurse(
                    id=assignment.employee_name,  # Mapping name to id for UI display if needed
                    name=assignment.employee_name,
                    shift_hours=8.0,  # Placeholder or from domain
                    scheduling_rationale=", ".join(assignment.preference_conflicts),
                    role=assignment.employee_role,
                    is_agency=assignment.is_agency,
                )
            )

        return scheduling_pb2.DaySchedule(shifts=list(proto_shifts.values()))

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

            shift_date = shift.shift_start_dt.to_tz(facility_tz).date().format_common_iso()
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

    def _shift_name(self, shift_number: int) -> str:
        return {
            1: "Morning",
            2: "Afternoon",
            3: "Night",
        }.get(shift_number, f"Shift {shift_number}")

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
        base_by_unit = {
            101: 34,  # Short-term rehab
            102: 48,  # Long-term care
            103: 32,  # Memory care
            104: 24,  # Skilled/subacute
        }
        census = base_by_unit.get(shift.unit_id or 0, 36)
        if shift.shift_number == 3:
            census -= 2
        if shift.day_of_week in {whenever.Weekday(1), whenever.Weekday(5)}:
            census += 2
        if self._is_weekend(shift):
            census -= 1
        return max(census, 18)

    def _target_hrpd(self, shift: Shift) -> float:
        target_by_unit = {
            101: 3.9,
            102: 3.55,
            103: 3.7,
            104: 4.15,
        }
        target = target_by_unit.get(shift.unit_id or 0, 3.65)
        if shift.shift_number == 3:
            target -= 0.25
        if self._is_weekend(shift):
            target += 0.10
        return round(target, 2)

    @staticmethod
    def _is_weekend(shift: Shift) -> bool:
        return shift.day_of_week in {whenever.Weekday(6), whenever.Weekday(7)}
