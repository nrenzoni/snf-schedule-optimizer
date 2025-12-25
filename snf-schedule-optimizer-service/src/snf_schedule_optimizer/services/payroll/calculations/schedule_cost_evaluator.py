from __future__ import annotations

from collections import defaultdict

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Schedule,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.models.scheduling.schedule_cost_models import (
    CostBreakdown,
    ScheduleFinancialReport,
)
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.services.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)


class ScheduleCostEvaluator:
    def __init__(
        self,
        shift_pay_processor: ShiftPayProcessor,
    ):
        self.shift_pay_processor = shift_pay_processor

    async def evaluate_schedule(
        self,
        schedule: Schedule,
        data_provider: IScenarioDataProvider,
    ) -> ScheduleFinancialReport:
        # 1. Performance: Lookup Map for Employees (O(1) access)
        # Assuming provider has cached this efficiently
        employee_map = {
            e.employee_id: e for e in await data_provider.get_all_employees()
        }

        # 2. Performance: Pre-fetch shifts map (ID -> Object)
        all_shifts = {
            ShiftKey(s.facility_id, s.shift_id): s
            for s in data_provider.get_all_shifts()
        }

        # 3. Regroup Data: Group assignments by Employee to handle OT Logic
        # Structure: { employee_id: [Shift, Shift, ...] }
        emp_workload: dict[DomainPrimaryKeyType, list[Shift]] = defaultdict(list)

        # FIX: Iterate over string IDs, then look up the actual object
        for shift_id, emp_ids in schedule.shift_assignments.items():
            shift = all_shifts.get(shift_id)
            if not shift:
                # If the schedule references a shift not in our current context, skip it.
                continue

            for emp_id in emp_ids:
                emp_workload[emp_id].append(shift)

        # 4. Initialize Accumulators
        facility_costs: dict[DomainPrimaryKeyType, CostBreakdown] = defaultdict(
            CostBreakdown
        )
        role_costs: dict[str, CostBreakdown] = defaultdict(CostBreakdown)
        total_enterprise_cost = 0.0

        comp_service = data_provider.get_compensation_service()

        # 5. Calculate Cost per Employee (Time-Ordered)
        for emp_id, shifts in emp_workload.items():
            employee = employee_map.get(emp_id)
            if not employee:
                continue

            # CRITICAL: Sort shifts by time to calculate OT correctly
            # This ensures if a nurse works Facility A Mon-Wed and Facility B Thu-Fri,
            # Facility B correctly absorbs the Overtime cost.
            shifts.sort(key=lambda s: s.shift_start_dt)

            # Get history (hours worked BEFORE this schedule starts)
            # This ensures we know if the very first shift is already OT
            current_hours = await data_provider.get_accumulated_hours_for_pay_period(
                emp_id
            )

            for shift in shifts:
                # Calculate cost for this specific shift, knowing current accumulated hours
                # You might need to update calculate_shift_cost to accept current_hours
                # or perform the math here.
                facility_config = data_provider.get_facility_config(shift.facility_id)

                # 5b. Check Agency Status for THIS specific shift date
                # (Handles employees who convert from Agency -> Staff mid-period)
                comp_record = await comp_service.get_record_for_date(
                    shift.org_id,
                    employee.employee_id,
                    shift.shift_start_dt.date(),
                )

                # If no record exists, we can't accurately cost.
                # Skip or log error depending on strictness.
                if comp_record is None:
                    print(
                        f"Warning: No comp record for {emp_id} on {shift.shift_start_dt}"
                    )
                    continue

                is_agency = comp_record.is_agency

                # C. Calculate Cost
                cost_result = await self.shift_pay_processor.calculate_detailed_cost(
                    employee=employee,
                    shift=shift,
                    current_weekly_hours=current_hours,
                    facility_config=facility_config,
                )

                # Logic:
                duration = shift.duration_hours
                current_hours += duration

                # E. Map Results to Reporting Buckets
                if is_agency:
                    # For Agency, usually everything is "Agency Spend"
                    # But we can split OT if desired. Here we bundle base into agency_spend.
                    agency_amt = cost_result.base_wage
                    regular_amt = 0.0
                else:
                    agency_amt = 0.0
                    regular_amt = cost_result.base_wage

                breakdown = CostBreakdown(
                    regular_cost=regular_amt,
                    overtime_cost=cost_result.overtime_premium,
                    agency_spend=agency_amt,
                    bonuses=cost_result.incentive_bonuses,
                    total_hours=duration,
                )

                facility_costs[shift.facility_id] += breakdown
                role_costs[employee.job_title] += breakdown
                total_enterprise_cost += breakdown.total_cost

        return ScheduleFinancialReport(
            total_enterprise_cost=total_enterprise_cost,
            breakdown_per_facility=dict(facility_costs),
            breakdown_per_role=dict(role_costs),
        )
