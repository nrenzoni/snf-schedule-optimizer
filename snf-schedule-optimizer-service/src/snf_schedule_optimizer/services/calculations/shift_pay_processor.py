from typing import List

from snf_schedule_optimizer.models import DifferentialDateInterval, Employee, Shift, WorkedShiftSegment
from snf_schedule_optimizer.services.calculations.rule_eligibility_service import RuleEligibilityService
from snf_schedule_optimizer.services.interfaces import IEmployeeWorkHistoryService, IOvertimeCalculator, \
    IRateCalculator, IShiftSlicer, \
    IStaffCompensationService


class ShiftPayProcessor:
    """
    Manages the entire workflow to calculate the total pay for a nurse's shift.
    """

    def __init__(
            self,
            eligibility_service: RuleEligibilityService,
            ot_calculator: IOvertimeCalculator,
            slicer: IShiftSlicer,
            rate_calculator: IRateCalculator,
            compensation_service: IStaffCompensationService,
            work_history_service: IEmployeeWorkHistoryService,
    ):
        self.eligibility_service = eligibility_service
        self.ot_calculator = ot_calculator
        self.slicer = slicer
        self.rate_calculator = rate_calculator
        self.compensation_service = compensation_service
        self.work_history_service = work_history_service

    def calculate_shift_cost(self, employee: Employee, shift: Shift) -> float:

        comp_record = self.compensation_service.get_record_for_date(
            employee.employee_id,
            shift.shift_start_dt  # The date the shift begins
        )

        if comp_record is None:
            raise ValueError(
                f"No compensation record found for employee {employee.employee_id} on "
                f"{shift.shift_start_dt.to_date_string()}"
            )

        # Phase 1: Retrieve Inputs
        # Get rules applicable to this nurse
        differential_rules, overtime_rules = (
            self.eligibility_service.get_applicable_rules(employee, shift)
        )

        nurse_shift_history = self.work_history_service.get_processed_history_for_period(
            employee.employee_id,
            shift.shift_start_dt
        )

        # Convert abstract rules into concrete time intervals
        differential_intervals: List[DifferentialDateInterval] = []
        for rule in differential_rules:
            differential_intervals.extend(
                rule.get_applicable_intervals_for_shift(shift)
            )

        # Get concrete overtime intervals
        overtime_intervals = self.ot_calculator.get_overtime_intervals(
            shift,
            employee,
            nurse_shift_history,
            overtime_rules
        )

        # Phase 2: Slice the Shift
        segments: List[WorkedShiftSegment] = self.slicer.slice_shift(
            shift,
            differential_intervals,
            overtime_intervals,
        )

        # Phase 3: Calculate Total Cost
        total_cost = 0.0
        for segment in segments:
            cost = self.rate_calculator.calculate_effective_rate(comp_record, segment)
            total_cost += cost

        return total_cost
