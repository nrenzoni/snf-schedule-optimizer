import whenever
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase
from snf_schedule_optimizer.utils.sqlalchemy_types.instant_type import InstantType


class EmployeeRuleOverrideModel(SQLABase):
    """
    SQLAlchemy model representing the 'employee_rule_override' table.
    Used to store versioned overrides for specific employees.
    """

    __tablename__ = "employee_rule_override"

    org_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    effective_date: Mapped[whenever.Instant] = mapped_column(
        InstantType, primary_key=True
    )

    rounding_unit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_meal_deduction_enabled: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
