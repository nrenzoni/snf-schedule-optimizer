import whenever
from connectrpc.request import RequestContext

from snf_schedule_optimizer.api import MoveEmployeeRequest, OptimizationOutput
from snf_schedule_optimizer.generated.scheduling.v1 import (
    scheduling_connect,
    scheduling_pb2,
)
from snf_schedule_optimizer.services.scheduling.scheduler_facade import (
    WorkforceSchedulerService,
)


class SchedulingServiceHandler(scheduling_connect.SchedulingService):
    def __init__(self, scheduler_service: WorkforceSchedulerService):
        self.scheduler_service = scheduler_service

    async def get_monthly_schedule(
        self,
        request: scheduling_pb2.GetMonthlyScheduleRequest,
        ctx: RequestContext[
            scheduling_pb2.GetMonthlyScheduleRequest,
            scheduling_pb2.GetMonthlyScheduleResponse,
        ],
    ) -> scheduling_pb2.GetMonthlyScheduleResponse:
        return scheduling_pb2.GetMonthlyScheduleResponse()

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
        # 1. Map Proto Request -> Domain DTO
        domain_request = MoveEmployeeRequest(
            org_id=request.org_id,
            facility_id=request.facility_id,
            schedule_id=request.schedule_id,
            employee_id=request.employee_id,
            from_shift_id=request.from_shift_id or None,
            to_shift_id=request.to_shift_id or None,
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
        return self._map_to_optimization_response(result)

    def _map_to_optimization_response(
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
                    shift_id=assignment.shift_id,
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
