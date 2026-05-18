import whenever
from sqlalchemy import Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase
from snf_schedule_optimizer.utils.sqlalchemy_types.whenever_types import InstantType


class EmployeeRuleOverrideModel(SQLABase):
    """
    SQLAlchemy model representing the 'employee_rule_override' table.
    Used to store versioned overrides for specific employees.
    """

    __tablename__ = "employee_rule_override"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)

    effective_date: Mapped[whenever.Instant] = mapped_column(
        InstantType, primary_key=True
    )

    rounding_unit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_meal_deduction_enabled: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(EmployeeRuleOverrideModel.__table__)
