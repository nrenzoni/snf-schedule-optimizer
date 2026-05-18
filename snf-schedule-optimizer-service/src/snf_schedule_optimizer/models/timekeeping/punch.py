from __future__ import annotations

import dataclasses as dc
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import whenever

from snf_schedule_optimizer.models.constraints import PunchType
from snf_schedule_optimizer.models.main_data_models import EmployeeIdType
from snf_schedule_optimizer.models.scheduling.shift import Shift, ShiftKey

if TYPE_CHECKING:
    from snf_schedule_optimizer.domain.payroll.interfaces import (
        IDifferentialRule,
        IOvertimeRule,
    )


@dataclass(frozen=True)
class WorkedShiftSegment:
    """Represents a component of a shift, useful for OT / differential calculations."""

    parent_shift: Shift
    start_time: whenever.ZonedDateTime
    end_time: whenever.ZonedDateTime
    duration_hours: float = dc.field(init=False)

    applicable_differential_rules: list[IDifferentialRule]
    applicable_overtime_rules: list[IOvertimeRule]

    shift_code: str | None = None
    job_code: str | None = None
    cost_center_1: str | None = None
    cost_center_2: str | None = None

    rate_from_punch: float | None = None

    meal_not_taken: bool = False

    def __post_init__(self) -> None:
        duration = (self.end_time - self.start_time).in_hours()
        object.__setattr__(self, "duration_hours", duration)

    @property
    def ot_multiplier(self) -> float:
        multipliers: list[float] = []
        for rule in self.applicable_overtime_rules:
            m = rule.multiplier
            if m is None:
                continue
            try:
                multipliers.append(m)
            except (TypeError, ValueError):
                continue

        return max(multipliers) if multipliers else 1.0


@dataclass(frozen=True)
class WorkedHistoryFact:
    employee_id: EmployeeIdType
    shift_key: ShiftKey
    shift_start: str
    shift_end: str
    duration_hours: float


@dc.dataclass(frozen=True)
class WorkedTimeBlock:
    """A contiguous block of time that the employee was actively working."""

    employee_id: EmployeeIdType

    start_time: whenever.ZonedDateTime
    end_time: whenever.ZonedDateTime
    post_date: whenever.Date

    is_scheduled: bool = False

    shift_code: str | None = None
    job_code: str | None = None

    cost_center_1: str | None = None
    cost_center_2: str | None = None

    rate_from_punch: float | None = None
    meal_not_taken: bool = False


@dc.dataclass(frozen=True)
class TimePunch:
    """Represents a single raw time clock event (input from T&A system)."""

    employee_id: EmployeeIdType
    punch_time: whenever.ZonedDateTime
    raw_punch_id: UUID

    is_void: bool = False
    is_ignored: bool = False

    is_dragged_time: bool = False

    punch_type: PunchType | None = None

    shift_code: str | None = None
    job_code: str | None = None

    cost_center_1: str | None = None
    cost_center_2: str | None = None
    cost_center_3: str | None = None

    rate: float | None = None
    meal_not_taken: bool = False

    punch_recorded_at: whenever.Instant | None = None
