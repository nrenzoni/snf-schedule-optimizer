from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class ScheduleAssignmentModel(SQLABase):
    """
    Persisted record of an employee assigned to a shift within a specific schedule version.
    """

    __tablename__ = "schedule_assignment"

    # Composite PK often useful here
    schedule_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    org_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    facility_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    shift_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    employee_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
