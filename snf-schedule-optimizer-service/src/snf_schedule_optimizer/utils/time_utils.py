import pendulum
import math
from typing import Final


class TimeRoundingUtility:
    """Provides stateless utility functions for time manipulation."""

    @staticmethod
    def round_to_nearest_unit(
        dt: pendulum.DateTime, unit_minutes: int
    ) -> pendulum.DateTime:
        """
        Applies rounding logic to the nearest configured unit (e.g., 6-minute rule).
        This is a pure function.
        """
        # Ensure unit is positive
        if unit_minutes <= 0:
            return dt

        # Calculate total minutes since midnight
        # Note: We ensure the calculation respects the time components of the DateTime
        minutes_since_midnight = dt.hour * 60 + dt.minute + dt.second / 60.0

        # Calculate the closest multiple of the rounding unit
        rounded_minutes = round(minutes_since_midnight / unit_minutes) * unit_minutes

        # Convert back to hours, minutes, seconds
        new_hour = int(rounded_minutes // 60)
        new_minute = int(rounded_minutes % 60)

        # Use pendulum's set() method, which handles crossing midnight correctly
        # The result retains the original timezone and date unless the time components push it over 23:59.
        return dt.set(hour=new_hour, minute=new_minute, second=0, microsecond=0)
