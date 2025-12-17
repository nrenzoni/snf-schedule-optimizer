import datetime

import whenever
from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import SQLABase
from .employee import EmployeeModel


class EmployeeCertificationModel(SQLABase):
    """
    Represents a single certification record for an employee.
    Maps to the employee_certification table.
    """

    __tablename__ = "employee_certification"

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign Key to EmployeeModel
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employee.employee_id"), index=True
    )

    # Certification Metadata
    certification_name: Mapped[str] = mapped_column(String(50))
    acquired_date: Mapped[datetime.date] = mapped_column(Date)
    expiration_date: Mapped[datetime.date] = mapped_column(Date)

    # Status/Audit Fields
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_source: Mapped[str] = mapped_column(String(100))

    # Relationship to the Employee (Many Certifications belong to One Employee)
    employee: Mapped[EmployeeModel] = relationship(back_populates="certifications")

    def __repr__(self) -> str:
        return (
            f"<EmployeeCertificationModel("
            f"employee_id='{self.employee_id}', "
            f"cert='{self.certification_name}', "
            f"expires='{self.expiration_date}')>"
        )

    def is_valid_on_date(self, check_date: whenever.ZonedDateTime) -> bool:
        """
        Helper method to check if the certification is valid on a specific date.
        """
        # Convert whenever.Instant to Python datetime.date for comparison
        check_date_dt = check_date.date()

        # Certification is valid if the expiration date is greater than or equal to the check date.
        # AND the acquired date is less than or equal to the check date.
        return (
            whenever.Date.from_py_date(self.expiration_date)
            >= check_date_dt
            >= whenever.Date.from_py_date(self.acquired_date)
        )
