import enum
from typing import *

import pendulum
from dataclasses import dataclass
from enum import Enum
import polars as pl


# --- A. EHR / Acuity Data ---
@dataclass(frozen=True)
class ResidentAcuity:
    """Represents a single resident's current status and labor demand drivers."""
    resident_id: str
    unit_id: str
    census_day: pendulum.DateTime  # The day of the acuity capture
    pt_score_gg: int  # e.g., Functional status score (Section GG)
    nta_score: int  # Non-Therapy Ancillary comorbidity score
    clinical_category: str  # e.g., 'Acute Infection', 'Major Joint'


class PreferenceType(str, Enum):
    WEEKEND_OFF = "Weekend_Off"
    NIGHT_SHIFT_PREFERENCE = "Night_Shift_Preference"
    SPECIFIC_DAY_OFF = "Specific_Day_Off"
    DAY_SHIFT_PREFERENCE = "Day_Shift_Preference"


class DayOfWeek(str, Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


@dataclass(frozen=True)
class StaffPreference:
    """Represents a soft constraint derived from WFM self-service."""
    employee_id: str
    preference_type: PreferenceType
    specific_day: Optional[DayOfWeek]  # For SPECIFIC_DAY_OFF
    weight: float  # Used for LP penalty
    is_hard_block: bool  # If True, becomes a mandatory LP constraint


class NurseRole(str, Enum):
    RN = "RN"
    LPN = "LPN"
    CNA = "CNA"


# --- B. WFM / Staffing Data ---
@dataclass(frozen=True)
class NurseProfile:
    """Represents a single staff member's characteristics and constraints."""
    employee_id: str
    role: NurseRole
    hourly_cost_base: float  # Base wage
    ot_multiplier: float
    available_hours_weekly: int
    is_agency: bool
    skills: List[str]  # e.g., 'IV Therapy', 'Wound Care'
    custom_preferences: Optional[List[StaffPreference]] = None


@dataclass(frozen=True)
class MinMandates:
    """Immutable minimum staffing mandate from regulatory bodies."""
    min_rn_hprd: float  # Minimum HPRD for RNs
    min_lpn_hprd: float  # Minimum HPRD for LPNs
    min_cna_hprd: float  # Minimum HPRD for CNAs
    min_total_hprd: float  # Minimum total HPRD
    min_staff_per_shift_rn: int
    min_staff_per_shift_lpn: int
    min_staff_per_shift_cna: int


@dataclass(frozen=True)
class FacilityHrConfig:
    """Immutable facility HR policies."""
    max_weekly_hours_per_nurse: int
    min_rest_hours_between_shifts: int
    max_consecutive_work_days: int
    max_daily_hours_before_overtime: int
    max_total_hours_per_pay_period: int
    max_patient_to_staff_ratio: Optional[float]
    mandatory_days_off_after_max_consecutive_days: Optional[int]
    max_weekend_shifts_per_month: Optional[int]
    max_floating_assignments_per_month: Optional[int]  # how often nurses float between units
    require_annual_training: Optional[bool]
    max_night_shifts_per_month: Optional[int]


@dataclass(frozen=True)
class ShiftSpecificRequirements:
    """Immutable shift-specific staffing requirements."""
    target_hprd_rn: float
    target_hprd_lpn: float
    target_hprd_cna: float
    target_total_hprd: float


@dataclass(frozen=True)
class CrossShiftConstraints:
    """Immutable cross-shift staffing constraints."""
    max_total_hours_per_nurse_per_week: int
    min_days_off_per_week: int
    max_night_shifts_per_week: int


# --- C. Facility Configuration Data ---
@dataclass(frozen=True)
class FacilityConfig:
    """Immutable facility and HR compliance rules."""
    facility_id: str
    max_consecutive_shifts: int
    shifts_per_day: int


@dataclass(frozen=True)
class Schedule:
    assignments: Dict[str, List[int]]  # {employee_id: [shift_numbers]}
