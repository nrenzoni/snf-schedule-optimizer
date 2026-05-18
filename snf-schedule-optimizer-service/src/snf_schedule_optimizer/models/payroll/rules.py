from __future__ import annotations

import dataclasses as dc
from dataclasses import dataclass
from typing import TYPE_CHECKING

import whenever

from snf_schedule_optimizer.models.constraints import (
    DifferentialType,
    OvertimeTriggerType,
)

if TYPE_CHECKING:
    from snf_schedule_optimizer.domain.payroll.interfaces import (
        IDifferentialRule,
        IOvertimeRule,
    )


@dataclass
class Differential:
    name: str
    type: DifferentialType
    multiplier: float | None
    flat: float | None

    def __init__(
        self,
        name: str,
        d_type: DifferentialType,
        multiplier: float | None = None,
        flat: float | None = None,
    ):
        if (multiplier is None) == (flat is None):
            raise ValueError("Provide either multiplier or flat, not both or neither.")
        if d_type == DifferentialType.MULTIPLIER and multiplier is None:
            raise ValueError("Multiplier type requires a multiplier value.")
        if d_type == DifferentialType.FLAT and flat is None:
            raise ValueError("flat type requires a flat value.")

        self.name = name
        self.type = d_type
        self.multiplier = multiplier
        self.flat = flat


@dataclass(frozen=True)
class OvertimeInterval:
    start_dt: whenever.ZonedDateTime
    end_dt: whenever.ZonedDateTime
    applicable_rules: list[IOvertimeRule]


@dataclass(frozen=True)
class OvertimeTrigger:
    """Defines the condition for the rule to activate."""

    trigger_type: OvertimeTriggerType

    daily_threshold: float | None = None
    weekly_threshold: float | None = None

    work_period_start_day: whenever.Weekday | None = None
    work_period_start_time: whenever.Time | None = None

    daily_period_reset_time: whenever.Time | None = None

    consecutive_day_threshold: int | None = None

    consecutive_hours_threshold: float | None = None

    days_of_week_trigger: list[whenever.Weekday] | None = None


@dc.dataclass(frozen=True)
class DifferentialDateInterval:
    start_dt: whenever.ZonedDateTime
    end_dt: whenever.ZonedDateTime
    rule: IDifferentialRule | None
