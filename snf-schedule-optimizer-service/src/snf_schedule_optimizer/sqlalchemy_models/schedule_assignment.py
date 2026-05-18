from sqlalchemy import Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class ScheduleAssignmentModel(SQLABase):
    """
    Persisted record of an employee assigned to a shift within a specific schedule version.
    """

    __tablename__ = "schedule_assignment"
    __table_args__ = (
        Index("ix_schedule_assign_schedule", "schedule_version_id"),
        Index("ix_schedule_assign_employee_shift", "employee_id", "shift_id"),
        Index("ix_schedule_assign_shift", "shift_id"),
    )

    schedule_id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)
    schedule_version_id: Mapped[int | None] = mapped_column(
        Integer, index=True, nullable=True
    )

    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    shift_id: Mapped[int] = mapped_column(index=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(index=True, nullable=False)


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(ScheduleAssignmentModel.__table__)
