from __future__ import annotations

import datetime
import typing

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import SQLABase

if typing.TYPE_CHECKING:
    from .time_punch_model import TimePunchModel


class ShiftModel(SQLABase):
    """
    Represents the primary shift record (scheduled or worked).
    The Parent in the One-to-Many relationship with WorkedShiftSegmentModel.
    """

    __tablename__ = "shift"

    # --- Primary Key ---

    org_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    facility_id: Mapped[str] = mapped_column(String, primary_key=True, nullable=False)
    shift_id: Mapped[str] = mapped_column(String, primary_key=True)

    # --- Core Identity & Time ---
    shift_start_dt: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    shift_end_dt: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # --- Contextual Data (Required by Mapping and Rules Engine) ---

    # 1. Used in _map_shift_to_domain (Fixes previous errors)
    shift_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # e.g., '1', '2', '3'
    day_shift: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )  # True if Day Shift, False if Night Shift
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # e.g., pendulum.MONDAY (0), used for calculating weekend differential
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # The facility/shift's specific timezone (e.g., 'America/New_York')

    # 2. Scheduling & Role Data
    # Used for filtering rules by facility/unit
    unit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 3. Status
    is_scheduled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # True if this is a scheduled block; False if purely actual worked time

    # Relationship to TimePunches (New 1:N relationship)
    punches: Mapped[list[TimePunchModel]] = relationship(
        back_populates="shift_template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ShiftModel(id={self.shift_id}, start='{self.shift_start_dt}')>"
