import datetime

import whenever
from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKeyConstraint,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import DomainPrimaryKeyType, StaffCompensationRecord
from .base import SQLABase
from .nurse_profile import NurseProfileModel


class StaffCompensationModel(SQLABase):
    """
    SQLAlchemy ORM model for storing time-versioned financial rate data.
    Maps directly to the StaffCompensationRecord application dataclass.
    """

    __tablename__ = "staff_compensation_record"

    __table_args__ = (
        ForeignKeyConstraint(
            (
                "org_id",
                "employee_id",
            ),
            ["nurse_profile.org_id", "nurse_profile.employee_id"],
            name="fk_staff_comp_nurse_profile",
        ),
    )

    # --- Primary Key ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(index=True, nullable=False)

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
    union_contract_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    pay_grade_or_step: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Relationship Linkage ---
    nurse: Mapped["NurseProfileModel"] = relationship(back_populates="compensations")

    def __repr__(self) -> str:
        return (
            f"<StaffCompensationModel("
            f"id={self.id}, employee_id='{self.employee_id}', "
            f"rate={self.base_rate_effective}, "
            f"start_date={self.effective_start_date})>"
        )

    def to_domain(self) -> StaffCompensationRecord:
        return StaffCompensationRecord(
            employee_id=self.employee_id,
            base_rate_effective=float(self.base_rate_effective),
            ot_multiplier=self.ot_multiplier,
            is_agency=self.is_agency,
            # Map datetime.date from DB to whenever.Instant
            effective_start_date=whenever.Date.from_py_date(self.effective_start_date),
            effective_end_date=whenever.Date.from_py_date(self.effective_end_date)
            if self.effective_end_date
            else None,
            union_contract_id=self.union_contract_id,
            pay_grade_or_step=self.pay_grade_or_step,
        )

    @staticmethod
    def from_domain(
        record: StaffCompensationRecord,
        org_id: DomainPrimaryKeyType,
    ) -> "StaffCompensationModel":
        effective_end_date = (
            record.effective_end_date.py_date() if record.effective_end_date else None
        )

        return StaffCompensationModel(
            org_id=org_id,
            employee_id=record.employee_id,
            base_rate_effective=record.base_rate_effective,
            ot_multiplier=record.ot_multiplier,
            is_agency=record.is_agency,
            effective_start_date=record.effective_start_date.py_date(),
            effective_end_date=effective_end_date,
            union_contract_id=record.union_contract_id,
            pay_grade_or_step=record.pay_grade_or_step,
        )


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(StaffCompensationModel.__table__)
