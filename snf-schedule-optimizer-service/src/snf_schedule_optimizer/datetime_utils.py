import pendulum


def is_weekend(day_of_week: pendulum.WeekDay) -> bool:
    """Helper to determine if a given day is a weekend."""
    return day_of_week in {pendulum.WeekDay.SATURDAY, pendulum.WeekDay.SUNDAY}


def is_between(
        check_time: pendulum.DateTime,
        start_time: pendulum.DateTime,
        end_time: pendulum.DateTime,
) -> bool:
    return start_time < check_time < end_time
