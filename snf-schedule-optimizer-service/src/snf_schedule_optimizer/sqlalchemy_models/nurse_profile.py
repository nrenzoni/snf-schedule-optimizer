from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, BigInteger, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snf_schedule_optimizer.models import DomainPrimaryKeyType, NurseProfile
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase
from snf_schedule_optimizer.sqlalchemy_models.staff_shift_preference import (
    StaffShiftPreferenceModel,
)

if TYPE_CHECKING:
    from snf_schedule_optimizer.sqlalchemy_models.staff_compensation_model import (
        StaffCompensationModel,
    )


class NurseProfileModel(SQLABase):
    """
    SQLAlchemy model representing the 'nurse_profile' table.
    """

    __tablename__ = "nurse_profile"

    org_id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(primary_key=True)

    available_hours_weekly: Mapped[float] = mapped_column(Float, default=40.0)

    # Skills stored as a comma-separated string for simplicity
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    compensations: Mapped[list["StaffCompensationModel"]] = relationship(
        back_populates="nurse",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    primary_unit_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )

    # One-to-many relationship with preferences
    preferences: Mapped[list["StaffShiftPreferenceModel"]] = relationship(
        # "StaffShiftPreferenceModel",
        back_populates="nurse",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eagerly load preferences to avoid N+1 issues in async domain conversion
    )

    def to_domain(self) -> NurseProfile:
        return NurseProfile(
            employee_id=self.employee_id,
            available_hours_weekly=self.available_hours_weekly,
            skills=self.skills,
            shift_custom_preferences=[p.to_domain() for p in self.preferences],
            primary_unit_id=self.primary_unit_id,
        )

    @staticmethod
    def from_domain(
        org_id: DomainPrimaryKeyType,
        domain: NurseProfile,
    ) -> "NurseProfileModel":
        if domain.shift_custom_preferences:
            custom_preferences_ = [
                StaffShiftPreferenceModel.from_domain(domain.employee_id, p)
                for p in domain.shift_custom_preferences
            ]
        else:
            custom_preferences_ = []

        return NurseProfileModel(
            org_id=org_id,
            employee_id=domain.employee_id,
            available_hours_weekly=domain.available_hours_weekly,
            skills=domain.skills,
            preferences=custom_preferences_,
            primary_unit_id=domain.primary_unit_id,
        )
