from __future__ import annotations

import dataclasses as dc

import whenever

from snf_schedule_optimizer.models.main_data_models import (
    DomainPrimaryKeyType,
    EmployeeIdType,
)


@dc.dataclass(frozen=True)
class StaffCompensationRecord:
    """
    Represents a specific, auditable, time-bound financial rate record for an employee.
    This decouples the pay rate from the NurseProfile's scheduling constraints.
    """

    employee_id: EmployeeIdType

    base_rate_effective: float
    ot_multiplier: float
    is_agency: bool

    effective_start_date: whenever.Date
    effective_end_date: whenever.Date | None = None

    union_contract_id: DomainPrimaryKeyType | None = None
    pay_grade_or_step: str | None = None
