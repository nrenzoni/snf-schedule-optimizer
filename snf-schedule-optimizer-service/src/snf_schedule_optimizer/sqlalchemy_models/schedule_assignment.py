from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class ScheduleAssignmentModel(SQLABase):
    """
    Persisted record of an employee assigned to a shift within a specific schedule version.
    """

    __tablename__ = "schedule_assignment"

    # Composite PK often useful here
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)

    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    shift_id: Mapped[int] = mapped_column(index=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(index=True, nullable=False)
