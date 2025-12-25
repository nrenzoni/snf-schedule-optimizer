import whenever

from snf_schedule_optimizer.models import (
    DifferentialType,
    Employee,
    FacilityConfig,
    OvertimeInterval,
    OvertimeTrigger,
    OvertimeTriggerType,
    Shift,
    WorkedShiftSegment,
)
from snf_schedule_optimizer.optimizer.models import ShiftCostBreakdown
from snf_schedule_optimizer.services.hr.interfaces import IStaffCompensationRepo
from snf_schedule_optimizer.services.payroll.calculations.overtime_calculation import (
    ThresholdOvertimeRule,
)
from snf_schedule_optimizer.services.payroll.interfaces import (
    IShiftSlicer,
)
from snf_schedule_optimizer.services.payroll.rules.rule_eligibility_service import (
    RuleEligibilityService,
)


def _empty_breakdown() -> ShiftCostBreakdown:
    return ShiftCostBreakdown(0, 0, 0, 0, 0, 0)


class ShiftPayProcessor:
    """
    Manages the entire workflow to calculate the total pay for a nurse's shift.
    """

    def __init__(
        self,
        eligibility_service: RuleEligibilityService,
        # ot_calculator: IOvertimeCalculator,
        slicer: IShiftSlicer,
        compensation_service: IStaffCompensationRepo,
        # work_history_service: IEmployeeWorkHistoryService,
    ):
        self.eligibility_service = eligibility_service
        # self.ot_calculator = ot_calculator
        self.slicer = slicer
        self.compensation_service = compensation_service
        # self.work_history_service = work_history_service

    async def calculate_detailed_cost(
        self,
        employee: Employee,
        shift: Shift,
        current_weekly_hours: float,
        facility_config: FacilityConfig,
    ) -> ShiftCostBreakdown:
        comp_record = await self.compensation_service.get_record_for_date(
            shift.org_id,
            employee.employee_id,
            shift.shift_start_dt.start_of_day().date(),  # The date the shift begins
        )

        if comp_record is None:
            raise ValueError(
                f"No compensation record found for employee {employee.employee_id} on "
                f"{shift.shift_start_dt.format_iso()}"
            )

        # Determine Overtime Split (The "Projective" Logic)
        # We replace the heavy 'ot_calculator' with fast math for the optimizer
        duration = shift.duration_hours
        threshold = facility_config.overtime_threshold_hours_per_week

        # Calculate how much of THIS shift spills over the threshold
        hours_before_ot = max(0.0, threshold - current_weekly_hours)
        reg_hours = min(duration, hours_before_ot)
        ot_hours = max(0.0, duration - reg_hours)

        # 3. Create "Synthetic" Overtime Intervals for the Slicer
        # If we have OT, we assume it happens at the END of the shift
        # (Standard accounting practice for split shifts)
        overtime_intervals = []
        if ot_hours > 0:
            ot_start = shift.shift_end_dt.subtract(
                seconds=whenever.DateTimeDelta(hours=ot_hours).time_part().in_seconds(),
            )
            ot_end = shift.shift_end_dt
            synthetic_ot_rule = ThresholdOvertimeRule(
                name="Projected Weekly OT",
                multiplier=1.5,
                trigger=OvertimeTrigger(
                    trigger_type=OvertimeTriggerType.WEEKLY_HOURS,
                    weekly_threshold=threshold,
                    work_period_start_day=facility_config.start_of_work_week_day,
                    work_period_start_time=facility_config.start_of_work_day_time,
                ),
                priority=1,
            )
            overtime_intervals.append(
                OvertimeInterval(
                    start_dt=ot_start,
                    end_dt=ot_end,
                    applicable_rules=[synthetic_ot_rule],
                )
            )

        # 4. Get Differentials (Night/Weekend)
        # This remains the same, assuming eligibility_service is fast
        differential_rules, _ = await self.eligibility_service.get_applicable_rules(
            employee, shift
        )

        differential_intervals = []
        for rule in differential_rules:
            differential_intervals.extend(
                rule.get_applicable_intervals_for_shift(shift)
            )

        # 5. Slice the Shift
        # The slicer now chops the shift into segments like:
        # [7am-3pm (Reg)], [3pm-5pm (Reg + NightDiff)], [5pm-7pm (OT + NightDiff)]
        segments: list[WorkedShiftSegment] = self.slicer.slice_shift(
            shift,
            differential_intervals,
            overtime_intervals,
        )

        # 6. Calculate & Categorize Costs
        base_wage = 0.0
        ot_premium = 0.0
        diffs = 0.0

        for segment in segments:
            # Rate calculator needs to return the components, not just total
            # Assuming rate_calculator.calculate_components(record, segment) exists
            # If not, use your existing calculate_effective_rate and infer:

            # Simplified Logic:
            hourly_rate = comp_record.base_rate_effective

            # Base Cost (The straight time portion)
            segment_base = segment.duration_hours * hourly_rate

            # OT Premium (The extra portion, e.g., 0.5x)
            seg_ot_prem = 0.0
            if len(segment.applicable_overtime_rules) > 0:
                # We extract the multiplier from the rules attached to the interval.
                # Assuming simple aggregation (max) or taking the first rule.
                # Since we created it above, we know it has one rule.
                rules = segment.applicable_overtime_rules
                multiplier = max(r.multiplier for r in rules) if rules else 1.0

                # The premium is (Multiplier - 1.0) * Base
                # Example: 1.5x -> 1.0 Base + 0.5 Premium
                seg_ot_prem = segment_base * (multiplier - 1.0)

            # Differentials
            seg_diff = 0.0
            for diff in segment.applicable_differential_rules:
                differential = diff.differential
                if differential.type == DifferentialType.MULTIPLIER:
                    assert differential.multiplier is not None
                    seg_diff += (
                        differential.multiplier * hourly_rate * segment.duration_hours
                    )
                elif differential.type == DifferentialType.FLAT:
                    assert differential.flat is not None
                    seg_diff += differential.flat * segment.duration_hours

            base_wage += segment_base
            ot_premium += seg_ot_prem
            diffs += seg_diff

        return ShiftCostBreakdown(
            base_wage=base_wage,
            overtime_premium=ot_premium,
            shift_differentials=diffs,
            statutory_burden=0.0,  # Calculate outside or inject calculator
            benefits_burden=0.0,
            incentive_bonuses=0.0,
        )
