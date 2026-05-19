"""Domain value objects with built-in validation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    amount_cents: int

    def __post_init__(self) -> None:
        if self.amount_cents < 0:
            raise ValueError(f"Money cannot be negative: {self.amount_cents}")

    @property
    def dollars(self) -> float:
        return self.amount_cents / 100.0

    @classmethod
    def from_dollars(cls, dollars: float) -> "Money":
        return cls(amount_cents=round(dollars * 100))


@dataclass(frozen=True)
class Hours:
    total_minutes: int

    def __post_init__(self) -> None:
        if self.total_minutes < 0:
            raise ValueError(f"Hours cannot be negative: {self.total_minutes}")

    @property
    def as_float(self) -> float:
        return self.total_minutes / 60.0

    @classmethod
    def from_hours(cls, hours: float) -> "Hours":
        return cls(total_minutes=round(hours * 60))


@dataclass(frozen=True)
class StaffCount:
    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError(f"StaffCount cannot be negative: {self.count}")

