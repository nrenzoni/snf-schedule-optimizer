from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

import whenever
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase
from snf_schedule_optimizer.utils.sqlalchemy_types.whenever_types import InstantType

if TYPE_CHECKING:
    from snf_schedule_optimizer.sqlalchemy_models.shift import ShiftModel


class TimePunchModel(SQLABase):
    """
    Represents a single, raw time clock EVENT (IN, OUT, MEAL OUT, etc.)
    aligned with the TimePunch domain dataclass.
    """

    __tablename__ = "time_punch_raw_event"

    # --- Composite Foreign Key Constraint ---
    # This links (org_id, facility_id, shift_id) in this table
    # to (org_id, facility_id, shift_id) in the 'shift' table.
    __table_args__ = (
        ForeignKeyConstraint(
            (
                "org_id",
                "facility_id",
                "shift_id",
            ),
            ["shift.org_id", "shift.facility_id", "shift.id"],
            name="fk_time_punch_shift",
            ondelete="CASCADE",
        ),
        Index("ix_timepunch_employee", "employee_id"),
        Index("ix_timepunch_punch_time", "punch_time"),
    )

    # --- Core Identity & Time ---
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # NEW: Use UUID for raw_punch_id as it often corresponds to a GUID/UUID in source systems
    raw_punch_id: Mapped[uuid.UUID] = mapped_column(
        String(36), unique=True, nullable=False
    )

    employee_id: Mapped[int] = mapped_column(index=True, nullable=False)

    # CRITICAL CHANGE: Single time field for the event
    punch_time: Mapped[whenever.Instant] = mapped_column(InstantType, nullable=False)

    # --- Event Type & State Flags (For Pairing Logic) ---
    punch_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # e.g., 'CheckIn', 'CheckOut'
    is_void: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dragged_time: Mapped[bool] = mapped_column(Boolean, default=False)

    shift_id: Mapped[int] = mapped_column(index=True, nullable=False)
    shift_code: Mapped[str | None] = mapped_column(String, nullable=False)

    # --- Cost Allocation Fields ---
    job_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_center_1: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_center_2: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_center_3: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Audit & Metadata ---
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    meal_not_taken: Mapped[bool] = mapped_column(Boolean, default=False)
    punch_recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )  # When system logged it

    # Relationship Linkage
    shift_template: Mapped[ShiftModel | None] = relationship(back_populates="punches")

    def __repr__(self) -> str:
        return (
            f"<TimePunchModel(id={self.id}, emp={self.employee_id}, "
            f"type='{self.punch_type}', time='{self.punch_time}')>"
        )


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(TimePunchModel.__table__)
