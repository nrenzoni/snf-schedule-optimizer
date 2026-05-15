from typing import TYPE_CHECKING

import whenever
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import DomainPrimaryKeyType, Employee, EmploymentClassification
from ..utils.sqlalchemy_types.whenever_types import DateType
from .base import SQLABase

if TYPE_CHECKING:
    from .employee_certification import EmployeeCertificationModel


class EmployeeModel(SQLABase):
    """
    SQLAlchemy model representing the 'employee' table.
    """

    __tablename__ = "employee"

    org_id: Mapped[int] = mapped_column(primary_key=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str] = mapped_column(String(50), nullable=False)

    hire_date: Mapped[whenever.Date] = mapped_column(DateType, nullable=False)

    classification: Mapped[str] = mapped_column(
        String(10), nullable=False, default="FT"
    )

    certifications: Mapped[list["EmployeeCertificationModel"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )

    def to_domain(self) -> Employee:
        return Employee(
            employee_id=self.id,
            name=str(self.name),
            job_title=str(self.job_title),
            hire_date=self.hire_date,
            classification=EmploymentClassification(self.classification),
        )

    @staticmethod
    def from_domain(
        org_id: DomainPrimaryKeyType,
        domain: Employee,
    ) -> "EmployeeModel":
        return EmployeeModel(
            id=domain.employee_id,
            org_id=org_id,
            name=domain.name,
            job_title=domain.job_title,
            hire_date=domain.hire_date,
            classification=domain.classification.value,
        )
