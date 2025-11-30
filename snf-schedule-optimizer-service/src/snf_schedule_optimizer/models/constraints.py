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
    CNA = "CNA"

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
