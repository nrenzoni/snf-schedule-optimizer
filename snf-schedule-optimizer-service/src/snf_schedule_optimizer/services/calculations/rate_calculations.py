from snf_schedule_optimizer.models import (
    DifferentialType,
    StaffCompensationRecord,
    WorkedShiftSegment,
)
from snf_schedule_optimizer.services.interfaces import IRateCalculator


class DifferentialAndOvertimeRateCalculator(IRateCalculator):
    # def calculate_effective_rate(
    #         self,
    #         employee: Employee,
    #         shift_granule: WorkedShiftSegment,
    # ) -> float:
    #     base = employee.hourly_cost_base * shift_granule.duration_hours
    #     if differential is None:
    #         return base
    #     if differential.type == DifferentialType.MULTIPLIER:
    #         assert differential.multiplier is not None
    #         return base * differential.multiplier
    #     elif differential.type == DifferentialType.FLAT:
    #         assert differential.flat is not None
    #         return base + differential.flat
    #     else:
    #         raise ValueError(f"Unknown DifferentialType: {differential.type}")

    def calculate_effective_rate(
        self,
        compensation_record: StaffCompensationRecord,
        segment: WorkedShiftSegment,
    ) -> float:
        # 1. Sum Differential Additions (FLAT) and Multipliers (for Regular Rate)
        total_differential_addition = 0.0
        differential_multiplier_sum = 0.0

        for rule in segment.applicable_differential_rules:
            diff = rule.differential
            if diff.type == DifferentialType.FLAT:
                assert diff.flat is not None
                total_differential_addition += diff.flat * segment.duration_hours
            elif diff.type == DifferentialType.MULTIPLIER:
                # Add (Multiplier - 1.0) to the Base Rate for the Regular Rate calculation
                assert diff.multiplier is not None
                differential_multiplier_sum += diff.multiplier - 1.0
            else:
                raise ValueError(f"Unknown DifferentialType: {diff.type}")

        # 1. Determine the Most Favorable Overtime Multiplier
        ot_multiplier = 1.0
        if segment.applicable_overtime_rules:
            # Find the highest multiplier required by any applicable rule
            ot_multiplier = max(
                rule.multiplier for rule in segment.applicable_overtime_rules
            )

        # 2. Calculate the Regular Rate of Pay (Base + Differentials)
        # Note: If Base Rate is $30 and Diff is 1.1x (10%), the rate is $30 * 1.1 = $33
        regular_rate_hourly = compensation_record.base_rate_effective * (
            1.0 + differential_multiplier_sum
        )

        # 3. Apply the Overtime Multiplier to the Regular Rate
        effective_rate_hourly = regular_rate_hourly * ot_multiplier

        # 4. Calculate total segment cost
        total_cost = (
            effective_rate_hourly * segment.duration_hours
        ) + total_differential_addition

        return total_cost
