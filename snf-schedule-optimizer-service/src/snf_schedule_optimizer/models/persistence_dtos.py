from dataclasses import dataclass

import whenever

from snf_schedule_optimizer.models import (
    DifferentialRuleType,
    DifferentialType,
    DomainPrimaryKeyType,
    EmployeeIdType,
    OvertimeTriggerType,
)


@dataclass(frozen=True)
class DifferentialRuleData:
    """Raw data representation of a differential rule from the DB."""

    rule_id: DomainPrimaryKeyType
    org_id: DomainPrimaryKeyType
    description: str
    priority: int
    rule_type: DifferentialRuleType
    differential_type: DifferentialType
    multiplier: float | None = None
    flat: float | None = None
    start_time: whenever.Time | None = None
    end_time: whenever.Time | None = None
    applicable_job_titles: list[str] | None = None
    contract_id: DomainPrimaryKeyType | None = None


@dataclass(frozen=True)
class OvertimeRuleData:
    """Raw data representation of an overtime rule from the DB."""

    rule_id: DomainPrimaryKeyType
    org_id: DomainPrimaryKeyType
    description: str
    multiplier: float
    priority: int

    # Trigger Config
    trigger_type: OvertimeTriggerType
    daily_threshold: float | None = None
    weekly_threshold: float | None = None
    consecutive_day_threshold: int | None = None
    consecutive_hours_threshold: float | None = None

    work_period_start_day: whenever.Weekday | None = None
    work_period_start_time: whenever.Time | None = None
    daily_period_reset_time: whenever.Time | None = None
    days_of_week_trigger: list[whenever.Weekday] | None = None

    applicable_job_titles: list[str] | None = None
    required_certifications: list[str] | None = None
    certification_match_type: str = "ALL"
    contract_id: DomainPrimaryKeyType | None = None


@dataclass(frozen=True)
class EmployeeCertificationData:
    """Strongly typed data structure for certification records."""

    employee_id: EmployeeIdType
    certification_name: str
    acquired_date: whenever.Date | None
    expiration_date: whenever.Date | None
