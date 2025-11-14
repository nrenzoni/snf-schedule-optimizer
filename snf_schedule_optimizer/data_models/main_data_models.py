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


# --- C. Facility Configuration Data ---
@dataclass(frozen=True)
class FacilityConfig:
    """Immutable facility and HR compliance rules."""
    facility_id: str
    target_hprd_rn: float  # CMS/State minimum HPRD for RNs
    max_consecutive_shifts: int
    base_cna_hprd_mandate: float  # CMS/State minimum HPRD for CNAs
    shifts_per_day: int
