from __future__ import annotations

from dataclasses import dataclass

from snf_schedule_optimizer.models.main_data_models import EmployeeIdType


@dataclass(frozen=True)
class EmployeeStateSnapshot:
    employee_id: EmployeeIdType
    worked_hours_day: float = 0.0
    worked_hours_week: float = 0.0
    worked_hours_pay_period: float = 0.0
    consecutive_days_worked: int = 0
    last_shift_end: str | None = None
    last_shift_type: str | None = None
