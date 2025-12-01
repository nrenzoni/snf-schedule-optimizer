import datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import SQLABase
from .employee import EmployeeModel


class StaffCompensationModel(SQLABase):
    """
    SQLAlchemy ORM model for storing time-versioned financial rate data.
    Maps directly to the StaffCompensationRecord application dataclass.
    """

    __tablename__ = "staff_compensation_record"

    # --- Primary Key ---
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Foreign Key to Employee (One Employee has Many Compensation Records) ---
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employee.employee_id"), index=True, nullable=False
    )

    # --- Rate and Multipliers ---
    # NUMERIC is best practice for monetary values in PostgreSQL
    base_rate_effective: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    ot_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    is_agency: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # --- Audit and Validity Period (Crucial for time-series data) ---
    effective_start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    effective_end_date: Mapped[datetime.date | None] = mapped_column(
        Date, nullable=True
    )

    # --- Metadata and Source ---
    union_contract_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pay_grade_or_step: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Relationship Linkage ---
    employee: Mapped[EmployeeModel] = relationship(
        back_populates="compensation_records"
    )

    def __repr__(self) -> str:
        return (
            f"<StaffCompensationModel("
            f"id={self.id}, employee_id='{self.employee_id}', "
            f"rate={self.base_rate_effective}, "
            f"start_date={self.effective_start_date})>"
        )
