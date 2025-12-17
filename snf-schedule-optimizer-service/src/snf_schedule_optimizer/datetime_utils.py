import whenever


def is_weekend(day_of_week: whenever.Weekday) -> bool:
    """Helper to determine if a given day is a weekend."""
    return day_of_week in {whenever.Weekday.SATURDAY, whenever.Weekday.SUNDAY}


def is_between(
    check_time: whenever.ZonedDateTime,
    start_time: whenever.ZonedDateTime,
    end_time: whenever.ZonedDateTime,
) -> bool:
    return start_time < check_time < end_time
