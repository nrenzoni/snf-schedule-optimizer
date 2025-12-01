from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import SQLABase

if TYPE_CHECKING:
    from .employee_certification import EmployeeCertificationModel


class EmployeeModel(SQLABase):
    """
    Represents the main employee identity table (Employee).
    """

    __tablename__ = "employee"

    # Primary Key
    employee_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    # Relationship to the certifications (One Employee has Many Certifications)
    certifications: Mapped[list["EmployeeCertificationModel"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
