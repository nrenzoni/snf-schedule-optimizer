from __future__ import annotations

import dataclasses as dc

import whenever

from snf_schedule_optimizer.models.constraints import (
    RoundingType,
    SplitDayType,
)
from snf_schedule_optimizer.models.main_data_models import EmployeeIdType


@dc.dataclass(frozen=True)
class EmployeeTimeSettings:
    """Configuration for punch pairing, rounding, and shift splitting boundaries."""

    pairing_threshold: whenever.DateTimeDelta

    split_day_threshold_time: whenever.Time | None

    split_day_day_type: SplitDayType | None

    shift_separator_time: whenever.Time | None

    shift_grace_window: whenever.DateTimeDelta

    rounding_unit_minutes: int

    rounding_type: RoundingType | None

    shift_seperator_enabled: bool = False


@dc.dataclass(frozen=True)
class MealDeductionRules:
    """Defines the thresholds and parameters for mandatory deductions."""

    meal_threshold_hours: float

    meal_duration_hours: float

    meal_placement_hours: float | None = None

    is_mandatory: bool = True


@dc.dataclass(frozen=True)
class FacilityRulesConfig:
    """Strongly typed domain configuration for facility-wide rules."""

    rounding_unit_minutes: int
    meal_deduction_threshold_hours: float
    meal_deduction_duration_hours: float
    meal_is_mandatory: bool


@dc.dataclass(frozen=True)
class EmployeeRuleOverride:
    """Strongly typed overrides specific to an individual employee."""

    employee_id: EmployeeIdType
    rounding_unit_minutes: int | None = None
    auto_meal_deduction_enabled: bool | None = None
