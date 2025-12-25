from __future__ import annotations

import typing

import whenever
from sqlalchemy import Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import DomainPrimaryKeyType, Shift
from ..utils.sqlalchemy_types.whenever_types import InstantType
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

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    shift_id: Mapped[int] = mapped_column(index=True, nullable=False)

    # --- Core Identity & Time ---
    shift_start_dt: Mapped[whenever.Instant] = mapped_column(
        InstantType, nullable=False
    )
    shift_end_dt: Mapped[whenever.Instant] = mapped_column(InstantType, nullable=False)

    # --- Contextual Data (Required by Mapping and Rules Engine) ---

    # 1. Used in _map_shift_to_domain (Fixes previous errors)
    shift_number: Mapped[int | None] = mapped_column(
        nullable=True
    )  # e.g., '1', '2', '3'
    day_shift: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )  # True if Day Shift, False if Night Shift
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # e.g., pendulum.MONDAY (0), used for calculating weekend differential

    # 2. Scheduling & Role Data
    # Used for filtering rules by facility/unit
    unit_id: Mapped[int | None] = mapped_column(index=True, nullable=True)

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

    @staticmethod
    def from_domain(
        org_id: DomainPrimaryKeyType,
        domain_shift: Shift,
    ) -> ShiftModel:
        return ShiftModel(
            org_id=org_id,
            facility_id=domain_shift.facility_id,
            shift_id=domain_shift.shift_id,
            shift_start_dt=domain_shift.shift_start_dt.to_instant(),
            shift_end_dt=domain_shift.shift_end_dt.to_instant(),
            shift_number=domain_shift.shift_number,
            day_shift=domain_shift.day_shift,
            day_of_week=domain_shift.day_of_week.value,
            unit_id=domain_shift.unit_id,
            is_scheduled=domain_shift.is_scheduled,
        )
