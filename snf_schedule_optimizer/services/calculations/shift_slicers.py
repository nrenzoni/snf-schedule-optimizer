import itertools
from typing import List, Set

import pendulum

from snf_schedule_optimizer.models import DifferentialDateInterval, OvertimeInterval, Shift, WorkedShiftSegment
from snf_schedule_optimizer.services.interfaces import IDifferentialRule, IOvertimeRule, IShiftSlicer


class TimeOverlapShiftSlicer(IShiftSlicer):
    def slice_shift(
            self,
            shift: Shift,
            differential_intervals: List[DifferentialDateInterval],
            overtime_intervals: List[OvertimeInterval],
    ) -> List[WorkedShiftSegment]:

        shift_start = shift.shift_start_dt
        shift_end = shift.shift_end_dt

        # 1. Collect All Unique Boundary Points

        # Start with the shift's boundaries
        boundaries: Set[pendulum.DateTime] = {shift_start, shift_end}

        # Add all start/end points from differential intervals
        for diff_interval in differential_intervals:
            # Only add points that fall strictly within the shift or exactly at the start/end
            if shift_start < diff_interval.start_dt < shift_end:
                boundaries.add(diff_interval.start_dt)
            if shift_start < diff_interval.end_dt < shift_end:
                boundaries.add(diff_interval.end_dt)

        # Add all start/end points from overtime intervals
        for ot_interval in overtime_intervals:
            if shift_start < ot_interval.start_dt < shift_end:
                boundaries.add(ot_interval.start_dt)
            if shift_start < ot_interval.end_dt < shift_end:
                boundaries.add(ot_interval.end_dt)

        # 2. Sort the Boundaries to create contiguous segments
        # Filter out any points outside the shift (though careful filtering above should prevent this)
        sorted_boundaries = sorted(t for t in boundaries if shift_start <= t <= shift_end)

        # Ensure only unique boundaries remain (set conversion handled this, but sort removes duplicates cleanly)

        final_segments: List[WorkedShiftSegment] = []

        # 3. Iterate through sorted boundaries to create segments (bins)
        for i in range(len(sorted_boundaries) - 1):
            segment_start = sorted_boundaries[i]
            segment_end = sorted_boundaries[i + 1]

            # Skip zero-duration segments
            if segment_start == segment_end:
                continue

            # The midpoint is used to check which continuous rule sets apply to this segment
            duration = segment_end - segment_start
            # Use total_seconds/2 to get the precise midpoint time
            midpoint = segment_start.add(seconds=duration.total_seconds() / 2)

            # --- 4. Assign Applicable Rules to the Segment ---

            active_diff_rules: Set[IDifferentialRule] = set()
            active_ot_rules: Set[IOvertimeRule] = set()

            # A. Assign Differential Rules
            for diff_interval in differential_intervals:
                # Check if the midpoint falls within the interval's time span
                if diff_interval.start_dt <= midpoint < diff_interval.end_dt:
                    assert diff_interval.rule is not None
                    active_diff_rules.add(diff_interval.rule)

            # B. Assign Overtime Rules
            for ot_interval in overtime_intervals:
                # Check if the midpoint falls within the interval's time span
                if ot_interval.start_dt <= midpoint < ot_interval.end_dt:
                    # Flatten the list of rules associated with this interval
                    for rule in ot_interval.applicable_rules:
                        active_ot_rules.add(rule)

            # 5. Create the Final Segment
            final_segments.append(
                WorkedShiftSegment(
                    # employee_id=,
                    parent_shift=shift,
                    start_time=segment_start,
                    end_time=segment_end,

                    # Convert sets back to lists for the dataclass
                    applicable_differential_rules=list(active_diff_rules),
                    applicable_overtime_rules=list(active_ot_rules),
                )
            )

        # 6. Production Quality Check (Ensure total duration is conserved)
        # This check helps catch off-by-one errors or missed boundaries.
        if final_segments:
            calculated_duration = sum((s.end_time - s.start_time).total_seconds() for s in final_segments)
            original_duration = (shift_end - shift_start).total_seconds()

            # Use a small tolerance for float comparison
            if abs(calculated_duration - original_duration) > 0.001:
                # This should trigger an audit or logging event in production
                print(
                    f"CRITICAL ERROR: Shift {shift.shift_id} duration mismatch. Original: {original_duration}s, Calculated: {calculated_duration}s"
                )

        return final_segments
