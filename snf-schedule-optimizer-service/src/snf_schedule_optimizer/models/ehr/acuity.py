from __future__ import annotations

from dataclasses import dataclass

import whenever

from snf_schedule_optimizer.models.main_data_models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
)


@dataclass(frozen=True)
class ResidentAcuity:
    """Represents a single resident's current status and labor demand drivers."""

    resident_id: DomainPrimaryKeyType
    unit_id: DomainPrimaryKeyType
    census_day: whenever.ZonedDateTime
    pt_score_gg: int
    nta_score: int
    clinical_category: str
    pdpm_clinical_category: str | None = None


@dataclass(frozen=True)
class PTORequest:
    employee_id: EmployeeIdType
    date: whenever.Date
    hours: float = 0.0


@dataclass(frozen=True)
class MlModelOutputs:
    """Stores the pre-calculated, dynamic outputs from ML models."""

    turnover_risk_scores: dict[int, float]
    shift_call_out_forecast: float
    unit_acuity_stress: dict[DomainPrimaryKeyType, float]
    team_compatibility_scores: dict[tuple[str, str], float]
