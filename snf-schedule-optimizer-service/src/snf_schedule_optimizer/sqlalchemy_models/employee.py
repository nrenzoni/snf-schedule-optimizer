from typing import TYPE_CHECKING

import whenever
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Employee
from ..utils.sqlalchemy_types.instant_type import InstantType
from .base import SQLABase

if TYPE_CHECKING:
    from .employee_certification import EmployeeCertificationModel


class EmployeeModel(SQLABase):
    """
    SQLAlchemy model representing the 'employee' table.
    """

    __tablename__ = "employee"

    org_id: Mapped[str] = mapped_column(nullable=False, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str] = mapped_column(String(50), nullable=False)

    # Hire date stored as UTC in the database
    hire_date: Mapped[whenever.Instant] = mapped_column(InstantType, nullable=False)

    certifications: Mapped[list["EmployeeCertificationModel"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )

    def to_domain(self) -> Employee:
        """
        Converts the database model to the domain Employee entity.
        """
        hire_instant = self.hire_date

        return Employee(
            employee_id=str(self.employee_id),
            name=str(self.name),
            job_title=str(self.job_title),
            hire_date=hire_instant.to_tz("UTC").date(),
        )
