from collections import defaultdict

import whenever
from connectrpc.request import RequestContext
from returns.result import Failure, Result, Success, safe

from snf_schedule_optimizer.api import MoveEmployeeRequest, OptimizationOutput
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
from snf_schedule_optimizer.infrastructure.sqid_converter import (
    IIdObfuscator,
)
from snf_schedule_optimizer.models import ShiftKey
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
        scheduler_service: WorkforceSchedulerFacadePort,
        facility_facade: FacilityFacade,
        id_obfuscator: IIdObfuscator,
    ):
        self.scheduler_service = scheduler_service
        self.facility_facade = facility_facade
        self.id_obfuscator = id_obfuscator

    async def get_all_org_facilities(
        self,
        request: scheduling_dot_v1_dot_scheduling__pb2.GetAllOrgFacilitiesRequest,
        ctx: RequestContext[GetAllOrgFacilitiesRequest, GetAllOrgFacilitiesResponse],
    ) -> scheduling_dot_v1_dot_scheduling__pb2.GetAllOrgFacilitiesResponse:
        facility_configs = await self.facility_facade.get_all_system_facilities()
        org_facs = [
            scheduling_dot_v1_dot_scheduling__pb2.OrgFacility(
                org_id=self.id_obfuscator.encode(facility.org_id),
                facility_id=self.id_obfuscator.encode(facility.facility_id),
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

        schedule, shifts, employees, facility_config = (
            await self.scheduler_service.get_monthly_schedule(
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
            facility_id=self.id_obfuscator.encode(facility_config.facility_id),
        )
        response.schedules.update(day_schedules)
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
        result: OptimizationOutput = await self.scheduler_service.validate_shift_move(
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
            response.financials.CopyFrom(
                scheduling_pb2.FinancialReport(
                    total_enterprise_cost=result.financials.total_enterprise_cost,
                    total_incentive_cost=sum(
                        f.bonuses
                        for f in result.financials.breakdown_per_facility.values()
                    ),
                    total_overtime_cost=sum(
                        f.overtime_cost
                        for f in result.financials.breakdown_per_facility.values()
                    ),
                    regular_pay_cost=sum(
                        f.regular_cost
                        for f in result.financials.breakdown_per_facility.values()
                    ),
                )
            )

        # Map Statistics
        if result.stats:
            response.stats.CopyFrom(
                scheduling_pb2.OptimizationStats(
                    execution_time_ms=result.stats.execution_time_ms,
                    objective_value=result.stats.objective_value or 0.0,
                    total_variables=result.stats.total_variables,
                    total_constraints=result.stats.total_constraints,
                )
            )

        # Map Updated Schedule (Visual feedback for the UI)
        if result.schedule and result.analysis:
            response.updated_schedule.CopyFrom(self._map_to_day_schedule(result))

        return response

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
                )
            )

        return scheduling_pb2.DaySchedule(shifts=list(proto_shifts.values()))

    def _map_monthly_schedule(
        self,
        schedule: scheduling_pb2.GetMonthlyScheduleResponse | object,
        shifts: dict[ShiftKey, object],
        employees: dict[int, object],
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
                    )
                )

            actual_hours = sum(nurse.shift_hours for nurse in nurse_messages)
            target_hrpd = 3.5
            patient_census = 36 if shift.day_shift else 28
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
