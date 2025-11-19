import pendulum


def is_weekend(day_of_week: pendulum.WeekDay) -> bool:
    """Helper to determine if a given day is a weekend."""
    return day_of_week in {pendulum.WeekDay.SATURDAY, pendulum.WeekDay.SUNDAY}
