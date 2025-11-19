from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import *

import pendulum


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


class PreferenceType(StrEnum):
    WEEKEND_OFF = "Weekend_Off"
    NIGHT_SHIFT_PREFERENCE = "Night_Shift_Preference"
    SPECIFIC_DAY_OFF = "Specific_Day_Off"
    DAY_SHIFT_PREFERENCE = "Day_Shift_Preference"


@dataclass(frozen=True)
class StaffPreference:
    """Represents a soft constraint derived from WFM self-service."""
    # employee_id: str
    preference_type: PreferenceType
    specific_day: Optional[pendulum.WeekDay]  # For SPECIFIC_DAY_OFF
    penalty_weight: float
    is_hard_block: bool  # If True, becomes a mandatory LP constraint


class NurseRole(StrEnum):
    RN = "RN"
    LPN = "LPN"
    CNA = "CNA"


NURSE_ROLES = [NurseRole.RN, NurseRole.LPN, NurseRole.CNA]


# --- B. WFM / Staffing Data ---
@dataclass(frozen=True)
class NurseProfile:
    """Represents a single staff member's characteristics and constraints."""
    employee_id: str
    role: NurseRole
    hourly_cost_base: float  # Base wage, agency adjusted here
    ot_multiplier: float  # non-exempt OT pay multiplier, if exempt set to 1.0
    available_hours_weekly: int
    is_agency: bool
    skills: List[str]  # e.g., 'IV Therapy', 'Wound Care'
    custom_preferences: Optional[List[StaffPreference]] = None


@dataclass(frozen=True)
class NurseShiftData:
    """Represents data of single shift assignment for a nurse."""
    is_ot: bool


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
    min_rest_hours_between_shifts: float
    max_consecutive_work_days: int
    max_total_hours_per_pay_period: int
    max_patient_to_staff_ratio: Optional[float]
    mandatory_days_off_after_max_consecutive_days: Optional[int]  # if provided, must be greater than 0
    max_weekend_shifts_per_month: Optional[int]
    max_floating_assignments_per_month: Optional[int]  # how often nurses float between units
    max_night_shifts_per_month: Optional[int]
    require_annual_training: Optional[bool]


@dataclass(frozen=True)
class ShiftSpecificRequirements:
    """Immutable shift-specific staffing requirements."""
    target_hprd_rn: float
    # target_hprd_lpn: float
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
    shifts_per_day: int
    overtime_threshold_hours_per_week: int
    start_of_work_week_day: pendulum.WeekDay
    start_of_work_day_time: pendulum.Time
    pay_period: pendulum.Duration
    weekend_multiplier: float
    night_shift_multiplier: float


@dataclass(frozen=True)
class Shift:
    shift_id: str
    shift_number: int
    day_shift: bool
    day_of_week: pendulum.WeekDay
    shift_start_dt: pendulum.DateTime
    shift_end_dt: pendulum.DateTime
    timezone: pendulum.Timezone

    @property
    def duration_hours(self) -> float:
        return (self.shift_end_dt - self.shift_start_dt).total_hours()

    def __hash__(self) -> int:
        return hash(self.shift_id)


@dataclass(frozen=True)
class Schedule:
    shift_assignments: Dict[str, List[str]]  # {Shift: [employee_ids]}


@dataclass(frozen=True)
class NurseShiftHourComponent:
    shift: Shift
    start_time: pendulum.DateTime
    end_time: pendulum.DateTime
    is_ot: bool

    @property
    def duration_hours(self) -> float:
        return (self.end_time - self.start_time).total_hours()


@dataclass(frozen=True)
class PreferenceWeights:
    ot_avoidance_penalty: float = 1000.0
    team_consistency_penalty: float = 300.0
    high_risk_shift_penalty: float = 2000.0
    custom_preference_penalty: float = 1500.0


@dataclass(frozen=True)
class MlModelOutputs:
    """Stores the pre-calculated, dynamic outputs from ML models."""
    turnover_risk_scores: Dict[str, float]  # {employee_id: score}
    shift_call_out_forecast: float  # {shift_id: predicted_rate}
    unit_acuity_stress: Dict[str, float]  # {unit_id: stress_multiplier}
    team_compatibility_scores: Dict[Tuple[str, str], float]  # {(nurse_A, nurse_B): score}


class DifferentialType(StrEnum):
    MULTIPLIER = "MULTIPLIER"
    FLAT = "FLAT"


@dataclass
class Differential:
    name: str
    type: DifferentialType
    multiplier: Optional[float]
    flat: Optional[float]

    def __init__(
            self,
            name: str,
            type: DifferentialType,
            multiplier: Optional[float] = None,
            flat: Optional[float] = None,
    ):
        if (multiplier is None) == (flat is None):
            raise ValueError("Provide either multiplier or flat, not both or neither.")
        if type == DifferentialType.MULTIPLIER and multiplier is None:
            raise ValueError("Multiplier type requires a multiplier value.")
        if type == DifferentialType.FLAT and flat is None:
            raise ValueError("flat type requires a flat value.")

        self.name = name
        self.type = type
        self.multiplier = multiplier
        self.flat = flat
