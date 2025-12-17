import whenever


class TimeRoundingUtility:
    """Provides stateless utility functions for time manipulation."""

    @staticmethod
    def round_to_nearest_unit(
        dt: whenever.ZonedDateTime,
        unit_minutes: int,
    ) -> whenever.ZonedDateTime:
        """
        Applies rounding logic to the nearest configured unit (e.g., 6-minute rule).
        This is a pure function.
        todo: test
        """
        # Ensure unit is positive
        if unit_minutes <= 0:
            return dt

        return dt.round(
            "minute",
            increment=unit_minutes,
        )

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

    @staticmethod
    def start_of_week_date(d: whenever.Date) -> whenever.Date:
        # 1. Get the current ISO weekday value (Monday=1 ... Sunday=7)
        current_weekday = d.day_of_week().value

        # 2. Calculate days to subtract to get back to Monday (1)
        # If today is Monday (1), subtract 0. If Sunday (7), subtract 6.
        days_to_remove = current_weekday - 1

        # 3. Return the new date
        return d.subtract(days=days_to_remove)

    @staticmethod
    def start_of_week_zoned(zdt: whenever.ZonedDateTime) -> whenever.ZonedDateTime:
        # 1. Get the underlying Date
        d = zdt.date()

        # 2. Find the Monday date
        days_to_remove = d.day_of_week().value - 1
        monday_date = d.subtract(days=days_to_remove)

        # 3. Replace the date, then find the valid start of that day
        # Note: replace_date keeps the wall time, start_of_day resets it.
        return zdt.replace_date(monday_date).start_of_day()


def instant_to_zoned(
    instant: whenever.Instant,
    tz: str,
) -> whenever.ZonedDateTime:
    """Converts an Instant to a ZonedDateTime in the specified timezone."""
    return instant.to_tz(tz)
