import pytest

from snf_schedule_optimizer.domain.value_objects import (
    Hours,
    Money,
    StaffCount,
)


def test_money_creation() -> None:
    m = Money(amount_cents=1000)
    assert m.dollars == 10.0
    assert Money.from_dollars(10.0) == m


def test_money_negative_raises() -> None:
    with pytest.raises(ValueError):
        Money(amount_cents=-1)


def test_hours_creation() -> None:
    h = Hours(total_minutes=120)
    assert h.as_float == 2.0


def test_hours_negative_raises() -> None:
    with pytest.raises(ValueError):
        Hours(total_minutes=-1)


def test_staff_count_negative_raises() -> None:
    with pytest.raises(ValueError):
        StaffCount(count=-1)
