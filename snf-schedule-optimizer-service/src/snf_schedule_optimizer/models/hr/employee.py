from __future__ import annotations

from dataclasses import dataclass

import whenever

from snf_schedule_optimizer.models.constraints import (
    EmploymentClassification,
    PreferenceType,
)
from snf_schedule_optimizer.models.main_data_models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
)


@dataclass(frozen=True)
class StaffShiftPreference:
    """Represents a soft constraint derived from WFM self-service."""

    preference_type: PreferenceType
    specific_value: str | None
    penalty_weight: float
    is_hard_block: bool


@dataclass(frozen=True)
class EmployeeCertification:
    """Represents a single certification held by an employee with status data."""

    certification_name: str
    acquired_date: whenever.Instant
    expiration_date: whenever.Instant
    is_active: bool
    verification_source: str


@dataclass(frozen=True)
class Employee:
    """Represents a single staff member, tied to org.

    Aggregate Root: consistency boundary is the employee identity.
    """

    employee_id: EmployeeIdType
    name: str
    job_title: str
    hire_date: whenever.Date
    classification: EmploymentClassification = EmploymentClassification.FULL_TIME


@dataclass(frozen=True)
class NurseProfile:
    """Represents a single staff member's characteristics and constraints."""

    employee_id: EmployeeIdType
    available_hours_weekly: float
    skills: list[str] | None
    shift_custom_preferences: list[StaffShiftPreference] | None
    primary_unit_id: DomainPrimaryKeyType | None = None
    is_preceptor: bool = False
    is_charge_nurse: bool = False

    def __hash__(self) -> int:
        return hash(self.employee_id)
