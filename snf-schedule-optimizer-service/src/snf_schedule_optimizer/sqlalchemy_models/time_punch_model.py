import datetime
import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase

if TYPE_CHECKING:
    from snf_schedule_optimizer.sqlalchemy_models.shift import ShiftModel


class TimePunchModel(SQLABase):
    """
    Represents a single, raw time clock EVENT (IN, OUT, MEAL OUT, etc.)
    aligned with the TimePunch domain dataclass.
    """
    __tablename__ = 'time_punch_raw_event'

    # --- Core Identity & Time ---
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # NEW: Use UUID for raw_punch_id as it often corresponds to a GUID/UUID in source systems
    raw_punch_id: Mapped[uuid.UUID] = mapped_column(String(36), unique=True, nullable=False)

    employee_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    # CRITICAL CHANGE: Single time field for the event
    punch_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # --- Event Type & State Flags (For Pairing Logic) ---
    punch_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # e.g., 'CheckIn', 'CheckOut'
    is_void: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dragged_time: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Cost Allocation Fields ---
    shift_id: Mapped[Optional[int]] = mapped_column(ForeignKey('shift.id'), nullable=True)  # FK link
    shift_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    job_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cost_center_1: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cost_center_2: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cost_center_3: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # --- Audit & Metadata ---
    rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meal_not_taken: Mapped[bool] = mapped_column(Boolean, default=False)
    punch_recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )  # When system logged it

    # Relationship Linkage
    shift_template: Mapped[Optional['ShiftModel']] = relationship(back_populates='punches')

    def __repr__(self) -> str:
        return (f"<TimePunchModel(id={self.id}, emp={self.employee_id}, "
                f"type='{self.punch_type}', time='{self.punch_time}')>")
