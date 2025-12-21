from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple
from uuid import UUID

import whenever

from snf_schedule_optimizer.models import (
    DifferentialType,
    PreferenceType,
    PunchType,
    RoundingType,
    SplitDayType,
)

if TYPE_CHECKING:
    # These imports are only for type checking/static analysis, not runtime execution
    from snf_schedule_optimizer.services.payroll.interfaces import (
        IDifferentialRule,
        IOvertimeRule,
    )


# --- A. EHR / Acuity Data ---
@dataclass(frozen=True)
class ResidentAcuity:
    """Represents a single resident's current status and labor demand drivers."""

    resident_id: str
    unit_id: str
    census_day: whenever.ZonedDateTime  # The day of the acuity capture
    pt_score_gg: int  # e.g., Functional status score (Section GG)
    nta_score: int  # Non-Therapy Ancillary comorbidity score
    clinical_category: str  # e.g., 'Acute Infection', 'Major Joint'


@dataclass(frozen=True)
class StaffShiftPreference:
    """Represents a soft constraint derived from WFM self-service."""

    # employee_id: str
    preference_type: PreferenceType
    specific_value: str | None  # For SPECIFIC_DAY_OFF, UNIT_PREFERENCE, etc.
    penalty_weight: float  # not used yet
    is_hard_block: bool  # If True, becomes a mandatory LP constraint


@dataclasses.dataclass(frozen=True)
class EmployeeCertification:
    """Represents a single certification held by an employee with status data."""

    certification_name: str  # e.g., 'ACLS', 'Wound Care Specialist'
    acquired_date: whenever.Instant
    expiration_date: whenever.Instant
    is_active: bool  # Status flag for quick filtering
    verification_source: str  # e.g., 'State Board', 'Internal Training Record'
    # Optional: certification_number: str


@dataclass(frozen=True)
class Employee:
    """Represents a single staff member, tied to org."""

    employee_id: str
    name: str
    job_title: str
    hire_date: whenever.Date
    # certifications: Optional[List[str]]  # e.g., 'BLS', 'ACLS'  # moved to EmployeeCertification


# --- B. WFM / Staffing Data ---
@dataclass(frozen=True)
class NurseProfile:
    """Represents a single staff member's characteristics and constraints."""

    employee_id: str
    # role: NurseRole  # moved to job_title in Employee
    # base_rate: float  # Base wage, agency adjusted here
    # ot_multiplier: float  # non-exempt OT pay multiplier, if exempt set to 1.0
    available_hours_weekly: float
    # is_agency: bool
    skills: (
        list[str] | None
    )  # e.g., 'IV Therapy', 'Wound Care' perhaps turn into provider
    shift_custom_preferences: list[StaffShiftPreference] | None

    def __hash__(self) -> int:
        return hash(self.employee_id)


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
    max_patient_to_staff_ratio: float | None
    mandatory_days_off_after_max_consecutive_days: (
        int | None
    )  # if provided, must be greater than 0
    max_weekend_shifts_per_month: int | None
    max_floating_assignments_per_month: (
        int | None
    )  # how often nurses float between units
    max_night_shifts_per_month: int | None
    require_annual_training: bool | None


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

    org_id: str
    facility_id: str
    shifts_per_day: int
    overtime_threshold_hours_per_week: int
    start_of_work_week_day: whenever.Weekday
    start_of_work_day_time: whenever.Time
    pay_period: whenever.DateTimeDelta
    weekend_multiplier: float
    night_shift_multiplier: float
    tz: str


type FacilityIdKey = str
type ShiftIdKey = str


class ShiftKey(NamedTuple):
    facility_id: FacilityIdKey
    shift_id: ShiftIdKey


@dataclass(frozen=True)
class Shift:
    org_id: str
    shift_key: ShiftKey

    shift_number: int
    day_shift: bool
    day_of_week: whenever.Weekday
    shift_start_dt: whenever.ZonedDateTime
    shift_end_dt: whenever.ZonedDateTime

    def __post_init__(self) -> None:
        # Consistency Check: Ensure start/end are in the same facility timezone
        if self.shift_start_dt.tz != self.shift_end_dt.tz:
            raise ValueError(
                f"Shift {self.shift_id} start/end timezones mismatch: "
                f"{self.shift_start_dt.tz} vs {self.shift_end_dt.tz}"
            )

    @property
    def duration_hours(self) -> float:
        return self.shift_end_dt.difference(self.shift_start_dt).in_hours()

    # def __hash__(self) -> int:
    #     return hash((self.org_id, self.facility_id, self.shift_id))

    @property
    def facility_id(self) -> str:
        return self.shift_key.facility_id

    @property
    def shift_id(self) -> str:
        return self.shift_key.shift_id


type ShiftAssignmentsType = dict[ShiftKey, list[str]]


@dataclass(frozen=True)
class Schedule:
    """
    Represents the final output of the scheduling process.
    """

    org_id: str

    # facility_id is Optional because an "Enterprise Optimization" might return a Schedule containing assignments for multiple facilities.
    facility_id: str | None = None
    schedule_id: str | None = None  # Persistence ID

    # composite key prevents collisions in multi-facility reports. org_id not needed as this exists within an org context, i.e., class contains org_id
    shift_assignments: ShiftAssignmentsType = dataclasses.field(
        default_factory=dict
    )  # {(facility_id, shift_id): [employee_ids]}

    def get_assigned_employees(self, facility_id: str, shift_id: str) -> list[str]:
        key = ShiftKey(facility_id, shift_id)
        return self.shift_assignments.get(key, [])


@dataclass(frozen=True)
class WorkedShiftSegment:
    """Represents a component of a shift, useful for OT / differential calculations."""

    # employee_id: str
    parent_shift: Shift
    start_time: whenever.ZonedDateTime
    end_time: whenever.ZonedDateTime
    duration_hours: float = dataclasses.field(init=False)

    # --- Rule References (Crucial for Calculation & Audit) ---
    applicable_differential_rules: list[IDifferentialRule]
    applicable_overtime_rules: list[IOvertimeRule]

    # 1. Job and Cost Center References
    shift_code: str | None = None  # Code referencing the scheduled shift
    job_code: str | None = (
        None  # The specific job performed (e.g., 'Charge Nurse', 'ICU_RT')
    )
    cost_center_1: str | None = None  # Primary cost center (e.g., Unit 4B)
    cost_center_2: str | None = None  # Secondary cost center

    # 2. Financial Context
    rate_from_punch: float | None = (
        None  # Rate captured at punch time (for audit/cross-check)
    )

    # 3. Time Status
    meal_not_taken: bool = False  # Flag indicating a scheduled meal was skipped

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
class PreferenceWeights:
    ot_avoidance_penalty: float = 1000.0
    team_consistency_penalty: float = 300.0
    high_risk_shift_penalty: float = 2000.0
    custom_preference_penalty: float = 1500.0


@dataclass(frozen=True)
class MlModelOutputs:
    """Stores the pre-calculated, dynamic outputs from ML models."""

    turnover_risk_scores: dict[str, float]  # {employee_id: score}
    shift_call_out_forecast: float  # {shift_id: predicted_rate}
    unit_acuity_stress: dict[str, float]  # {unit_id: stress_multiplier}
    team_compatibility_scores: dict[
        tuple[str, str], float
    ]  # {(nurse_A, nurse_B): score}


@dataclass
class Differential:
    name: str
    type: DifferentialType
    multiplier: float | None
    flat: float | None

    def __init__(
        self,
        name: str,
        type: DifferentialType,
        multiplier: float | None = None,
        flat: float | None = None,
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


@dataclass(frozen=True)
class OvertimeInterval:
    start_dt: whenever.ZonedDateTime
    end_dt: whenever.ZonedDateTime
    applicable_rules: list[IOvertimeRule]


@dataclass(frozen=True)
class OvertimeTrigger:
    """Defines the condition for the rule to activate."""

    # --- Existing Fields (Required for basic FLSA/State OT) ---
    daily_threshold: float | None = None  # e.g., 8.0 hours
    weekly_threshold: float | None = None  # e.g., 40.0 hours

    # Weekly Work Period Definition (Crucial for FLSA)
    work_period_start_day: whenever.Weekday | None = None  # e.g., Monday
    work_period_start_time: whenever.Time | None = (
        None  # e.g., 12:01 AM (used to define the start of the 7-day work week)
    )

    # --- New Fields for Robust Configuration ---

    # 1. Daily Work Period Definition (CRUCIAL for Daily OT)
    daily_period_reset_time: whenever.Time | None = None
    # Used to define when the 24-hour day resets, important for shifts crossing midnight.
    # Example: If a facility's day is 6:00 AM to 6:00 AM, set this to 6:00 AM.

    # 2. Sequential Day Thresholds (Common in some US states like CA)
    # This rule triggers OT when an employee works a specific number of consecutive days.
    consecutive_day_threshold: int | None = None
    # e.g., 7 days. OT applies to the 7th day of work.

    # 3. Consecutive Hours Threshold (Important for long shifts)
    consecutive_hours_threshold: float | None = None
    # e.g., 12.0 hours. OT applies to any hours worked beyond 12 consecutive hours, regardless of daily/weekly totals.

    # 4. Specific Day Overtime (Common for mandated rest day OT)
    days_of_week_trigger: list[whenever.Weekday] | None = None
    # e.g., [pendulum.SUNDAY]. OT applies to all hours on this day, overriding other rules.


@dataclasses.dataclass(frozen=True)
class DifferentialDateInterval:
    start_dt: whenever.ZonedDateTime
    end_dt: whenever.ZonedDateTime
    rule: IDifferentialRule | None


@dataclasses.dataclass(frozen=True)
class StaffCompensationRecord:
    """
    Represents a specific, auditable, time-bound financial rate record for an employee.
    This decouples the pay rate from the NurseProfile's scheduling constraints.
    """

    # --- Identification ---
    employee_id: str

    # --- Rate and Multipliers ---
    base_rate_effective: (
        float  # The final hourly rate used before differentials/OT (e.g., 30.50)
    )
    ot_multiplier: float  # The default overtime multiplier for this record (e.g., 1.5)
    is_agency: bool  # Status for cost tracking and differential rule lookup

    # --- Audit and Validity Period ---
    effective_start_date: whenever.Date
    effective_end_date: whenever.Date | None = (
        None  # Nullable for records with no end date
    )

    # --- Metadata and Source ---
    union_contract_id: str | None = (
        None  # The specific contract/group driving this rate
    )
    pay_grade_or_step: str | None = None  # The internal pay scale identifier


@dataclasses.dataclass(frozen=True)
class WorkedTimeBlock:
    """A contiguous block of time that the employee was actively working."""

    employee_id: str  # Required for joining/tracking downstream

    start_time: whenever.ZonedDateTime
    end_time: whenever.ZonedDateTime
    post_date: (
        whenever.Date
    )  # The calendar day the hours are charged to (Crucial for splitting)

    # --- Status & Source ---
    is_scheduled: bool = False  # True if this block aligns with a scheduled shift

    # --- Cost Allocation Metadata (From TimePunch) ---
    shift_code: str | None = None  # Code referencing the scheduled shift
    job_code: str | None = None  # The job performed (e.g., 'Charge Nurse')

    # Cost Center Fields (Required for financial posting)
    cost_center_1: str | None = None  # Primary cost center (e.g., Unit 4B)
    cost_center_2: str | None = None  # Secondary cost center

    # Rate/Pay Data (Copied from TimePunch/Compensation Record)
    # The reconciler copies these fields over for quick reference before the final rate calculation.
    rate_from_punch: float | None = None
    meal_not_taken: bool = False


@dataclasses.dataclass(frozen=True)
class TimePunch:
    """Represents a single raw time clock event (input from T&A system)."""

    # --- Core Identity & Time ---
    employee_id: str
    punch_time: (
        whenever.ZonedDateTime
    )  # The actual time of the event (localTime/utcTime)
    raw_punch_id: UUID  # Unique ID from the source system (for audit linkage)

    # --- State Flags (From C# Logic) ---
    is_void: bool = False  # C#: x.r.isVoid == null || !x.r.isVoid.Value
    is_ignored: bool = False  # C#: x.r.ignored == null || !x.r.ignored.Value

    # NEW 1: Manual/Drag Time Flag (Crucial for filtering out manually adjusted punches)
    is_dragged_time: bool = False  # C#: !x.r.draggedTime.HasValue (We invert the check)

    # NEW 2: Punch Type (Crucial for pairing logic: CheckIn, CheckOut, MealOut)
    punch_type: PunchType | None = (
        None  # e.g., 'CheckIn', 'CheckOut' (C# 'punch1.type')
    )

    # --- Cost Allocation Fields (Corresponds to C# cc1, cc2, jobCode, shift) ---
    shift_code: str | None = (
        None  # Code referencing the scheduled shift (C#: punch1.shift)
    )
    job_code: str | None = None  # Job code for cost allocation (C#: punch1.jobCode)

    # NEW 3: Cost Center Fields (Mapped from generic C# cc1, cc2, cc3, etc.)
    cost_center_1: str | None = None  # C#: punch1.cc1
    cost_center_2: str | None = None  # C#: punch1.cc2
    cost_center_3: str | None = None  # C#: punch1.cc3

    # --- Audit & Metadata ---
    rate: float | None = None  # Rate from T&A (for cross-checking/costing)
    meal_not_taken: bool = False  # Flag from punch data (C#: punch1.mealNotTaken)

    # NEW 4: Punch Recorded Time (Crucial for Audit and Chronology)
    punch_recorded_at: whenever.Instant | None = (
        None  # When the punch record was created
    )


@dataclasses.dataclass(frozen=True)
class EmployeeTimeSettings:
    """Configuration for punch pairing, rounding, and shift splitting boundaries."""

    pairing_threshold: (
        whenever.DateTimeDelta
    )  # Max time between IN/OUT punches to match (Used in C# Pair)

    # --- Payroll Day Splitting/Crossover ---
    split_day_threshold_time: (
        whenever.Time | None
    )  # Time of day the payroll day resets (e.g., 3:00 AM)

    split_day_day_type: SplitDayType | None

    # Used to check if a block should be split across the daily cutoff.
    # Corresponds to 'shiftSeperator' used in IsSeparatedByShift.
    shift_separator_time: whenever.Time | None

    # Flag used in the splitting logic check (ShiftGraceWindow is usually a Duration)
    shift_grace_window: (
        whenever.DateTimeDelta
    )  # Window for checking if punches align with splits

    # --- Rounding ---
    rounding_unit_minutes: int  # Unit for rounding (e.g., 6, 15)

    # NEW 3: Used in the SplitPunches logic, although typically derived from rounding_unit
    rounding_type: RoundingType | None

    # NEW 4: Used to determine if the time is split/adjusted by a specific shift.
    # In C#, this often comes from the associated shift's metadata.
    # Although your model doesn't explicitly show this, it's a common necessary input.
    shift_seperator_enabled: bool = False


@dataclasses.dataclass(frozen=True)
class MealDeductionRules:
    """Defines the thresholds and parameters for mandatory deductions."""

    # Threshold duration for the shift that triggers the mandatory meal deduction
    meal_threshold_hours: float

    # Duration of the deduction itself (e.g., 0.5 for 30 minutes)
    meal_duration_hours: float

    # The time of day the meal period is typically placed (e.g., 5.0 for 5 hours into the shift)
    meal_placement_hours: float | None = None

    # Flag to indicate if the deduction is automatic, even if the employee did not punch out for it
    is_mandatory: bool = True


@dataclass(frozen=True)
class FacilityRulesConfig:
    """Strongly typed domain configuration for facility-wide rules."""

    rounding_unit_minutes: int
    meal_deduction_threshold_hours: float
    meal_deduction_duration_hours: float
    meal_is_mandatory: bool


@dataclass(frozen=True)
class EmployeeRuleOverride:
    """Strongly typed overrides specific to an individual employee."""

    employee_id: str
    rounding_unit_minutes: int | None = None
    auto_meal_deduction_enabled: bool | None = None
