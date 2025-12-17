from __future__ import annotations

from dataclasses import dataclass

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    ResidentAcuity,
    Shift,
    StaffCompensationRecord,
)


@dataclass
class PayBandConfig:
    """Defines pay rates for a specific tier (Low/Med/High)."""

    base_rate_rn: float
    base_rate_cna: float
    agency_premium_multiplier: float = 1.5  # Agency gets 1.5x base


@dataclass
class WorkforceConfig:
    count_rn: int = 100
    count_cna: int = 100
    percent_agency_rn: float = 0.10  # 0.0 to 1.0
    percent_agency_cna: float = 0.20

    # Probability of an employee falling into a pay band
    prob_pay_low: float = 0.33
    prob_pay_med: float = 0.33
    prob_pay_high: float = 0.34  # Should sum to 1.0


@dataclass
class HistoryConfig:
    """Defines buckets for accumulated hours at start of sim."""

    # Probabilities should sum to 1.0
    prob_zero_hours: float = 0.50
    prob_half_shift: float = 0.0
    prob_half_way_to_ot: float = 0.30  # e.g. 20 hours
    prob_near_ot: float = 0.20  # e.g. 38 hours


@dataclass
class PreferenceConfig:
    prob_no_preference: float = 0.60
    prob_no_nights: float = 0.10
    prob_no_weekends: float = 0.10
    prob_specific_day_off: float = 0.20


@dataclass
class TimeConfig:
    start_date: whenever.ZonedDateTime
    num_days: int = 3
    shifts_per_day: int = 3
    shift_duration_hours: int = 8


@dataclass
class AcuityConfig:
    """Controls generation of resident census and acuity levels."""

    base_census: int = 100
    high_acuity_probability: float = 0.15  # Chance of score 15 vs 5
    high_acuity_score: int = 15
    low_acuity_score: int = 5
    admission_surge_factor: float = 0.0  # Increase census by %


@dataclass
class ScenarioResult:
    """The output container holding all generated objects."""

    shifts: list[Shift]
    employees: list[Employee]
    nurses: list[NurseProfile]
    financials: list[StaffCompensationRecord]
    history_map: dict[str, float]  # employee_id -> hours
    preference_penalties: dict[str, float]  # pre-calculated penalties
    acuity_data: list[ResidentAcuity]
