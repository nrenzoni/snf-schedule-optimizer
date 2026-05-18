from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import whenever

from snf_schedule_optimizer.models.main_data_models import (
    DomainPrimaryKeyType,
)


class ShiftKey(NamedTuple):
    facility_id: DomainPrimaryKeyType
    shift_id: DomainPrimaryKeyType


@dataclass(frozen=True)
class Shift:
    org_id: DomainPrimaryKeyType
    shift_key: ShiftKey

    shift_number: int
    day_shift: bool
    day_of_week: whenever.Weekday
    shift_start_dt: whenever.ZonedDateTime
    shift_end_dt: whenever.ZonedDateTime
    unit_id: DomainPrimaryKeyType | None
    is_scheduled: bool

    def __post_init__(self) -> None:
        if self.shift_start_dt.tz != self.shift_end_dt.tz:
            raise ValueError(
                f"Shift {self.shift_id} start/end timezones mismatch: "
                f"{self.shift_start_dt.tz} vs {self.shift_end_dt.tz}"
            )

    @property
    def duration_hours(self) -> float:
        return self.shift_end_dt.difference(self.shift_start_dt).in_hours()

    @property
    def facility_id(self) -> int:
        return self.shift_key.facility_id

    @property
    def shift_id(self) -> int:
        return self.shift_key.shift_id


@dataclass(frozen=True)
class ShiftSpecificRequirements:
    """Immutable shift-specific staffing requirements."""

    target_hprd_rn: float
    target_hprd_cna: float
    target_total_hprd: float
    target_hprd_lpn: float = 0.0


@dataclass(frozen=True)
class CrossShiftConstraints:
    """Immutable cross-shift staffing constraints."""

    max_total_hours_per_nurse_per_week: int
    min_days_off_per_week: int
    max_night_shifts_per_week: int
