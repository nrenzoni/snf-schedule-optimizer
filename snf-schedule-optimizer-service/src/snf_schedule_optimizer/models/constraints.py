from enum import StrEnum


class PreferenceType(StrEnum):
    WEEKEND_OFF = "WEEKEND_OFF"
    NIGHT_SHIFT_PREFERENCE = "NIGHT_SHIFT_PREFERENCE"
    DAY_SHIFT_PREFERENCE = "DAY_SHIFT_PREFERENCE"
    SPECIFIC_DAY_OFF = "SPECIFIC_DAY_OFF"
    MAX_CONSECUTIVE_SHIFTS = "MAX_CONSECUTIVE_SHIFTS"
    UNIT_PREFERENCE = "UNIT_PREFERENCE"


class LookbackPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class PunchType(StrEnum):
    CHECK_IN = "CheckIn"
    CHECK_OUT = "CheckOut"
    MEAL_OUT = "MealOut"
    MEAL_IN = "MealIn"


class NurseRole(StrEnum):
    RN = "RN"
    LPN = "LPN"
    CNA = "CNA"


class HprdEnforcedRole(StrEnum):
    RN = "RN"
    LPN = "LPN"
    CNA = "CNA"


class OptimizationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizationRunStage(StrEnum):
    QUEUED = "queued"
    SNAPSHOTTING = "snapshotting"
    INDEXING = "indexing"
    BUILDING_MODEL = "building_model"
    SOLVING = "solving"
    ANALYZING = "analyzing"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"


class OptimizationFailureCode(StrEnum):
    SNAPSHOT_BUILD_FAILED = "snapshot_build_failed"
    BASELINE_INFEASIBLE = "baseline_infeasible"
    SOLVER_INFEASIBLE = "solver_infeasible"
    SOLVER_TIMEOUT = "solver_timeout"
    SOLVER_ERROR = "solver_error"
    PUBLISH_CONFLICT = "publish_conflict"
    PUBLISH_FAILED = "publish_failed"
    WORKER_ERROR = "worker_error"


class SolverTerminationReason(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE_NON_OPTIMAL = "feasible_non_optimal"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    INTERNAL_ERROR = "internal_error"


NURSE_ROLES = [NurseRole.RN, NurseRole.LPN, NurseRole.CNA]


class DifferentialType(StrEnum):
    MULTIPLIER = "MULTIPLIER"
    FLAT = "FLAT"


class SplitDayType(StrEnum):
    PREVIOUS = "Previous"  # Shift belongs to the previous day
    CURRENT = "Current"  # Shift belongs to the current day


class RoundingType(StrEnum):
    NEAREST = "Nearest"
    IN_FORWARD = "InForward"
    OUT_BACKWARD = "OutBackward"


class OvertimeTriggerType(StrEnum):
    DAILY_HOURS = "DAILY_HOURS"
    WEEKLY_HOURS = "WEEKLY_HOURS"
    CONSECUTIVE_DAYS = "CONSECUTIVE_DAYS"


class DifferentialRuleType(StrEnum):
    WEEKEND = "WEEKEND"
    NIGHT_SHIFT = "NIGHT_SHIFT"
    FIXED_TIME = "FIXED_TIME"
    ALL_HOURS = "ALL_HOURS"  # e.g., Float Pool or Lead Pay
