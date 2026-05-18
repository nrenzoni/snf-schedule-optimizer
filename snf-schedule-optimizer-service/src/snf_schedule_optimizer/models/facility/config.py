from __future__ import annotations

from dataclasses import dataclass, field

import whenever

from snf_schedule_optimizer.models.constraints import HprdEnforcedRole
from snf_schedule_optimizer.models.main_data_models import (
    DomainPrimaryKeyType,
)


@dataclass(frozen=True)
class MinMandates:
    """Immutable minimum staffing mandate from regulatory bodies."""

    min_rn_hprd: float
    min_lpn_hprd: float
    min_cna_hprd: float
    min_total_hprd: float
    min_staff_per_shift_rn: int
    min_staff_per_shift_lpn: int
    min_staff_per_shift_cna: int


@dataclass(frozen=True)
class FacilityHrConfig:
    """Immutable facility HR policies."""

    max_weekly_hours_per_nurse: int
    min_rest_hours_between_shifts: float
    max_consecutive_work_days: int
    max_total_hours_per_pay_period: int
    max_patient_to_staff_ratio: float | None
    mandatory_days_off_after_max_consecutive_days: int | None
    max_weekend_shifts_per_month: int | None
    max_floating_assignments_per_month: int | None
    max_night_shifts_per_month: int | None
    require_annual_training: bool | None


@dataclass(frozen=True)
class FacilityConfig:
    """Immutable facility and HR compliance rules."""

    org_id: DomainPrimaryKeyType
    facility_id: DomainPrimaryKeyType
    shifts_per_day: int
    overtime_threshold_hours_per_week: int
    start_of_work_week_day: whenever.Weekday
    start_of_work_day_time: whenever.Time
    pay_period: whenever.DateDelta
    weekend_multiplier: float
    night_shift_multiplier: float
    tz: str

    bi_weekly_ot_threshold: float = 80.0
    default_hprd_rn: float = 0.5
    default_hprd_lpn: float = 0.0
    default_hprd_cna: float = 2.4
    default_hprd_total: float = 3.5
    min_rest_hours_between_shifts: float = 10.0
    max_consecutive_work_days: int = 5
    max_total_hours_per_pay_period: float = 80.0
    agency_ot_multiplier: float = 1.5
    max_night_shifts_per_month: int | None = None
    max_weekend_shifts_per_month: int | None = None
    part_time_hour_fraction: float = 0.75
    pdpm_category_ratios: dict[str, dict[HprdEnforcedRole, float]] = field(
        default_factory=dict
    )
    holiday_dates: list[whenever.Date] = field(default_factory=list)
    min_circadian_rest_after_night: float = 11.0
    max_new_grads_per_preceptor: int = 2
    require_charge_nurse_per_shift: bool = False
