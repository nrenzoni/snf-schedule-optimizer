from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snf_schedule_optimizer.models import NurseProfile
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase

if TYPE_CHECKING:
    from snf_schedule_optimizer.sqlalchemy_models.staff_shift_preference import (
        StaffShiftPreferenceModel,
    )


class NurseProfileModel(SQLABase):
    """
    SQLAlchemy model representing the 'nurse_profile' table.
    """

    __tablename__ = "nurse_profile"

    org_id: Mapped[str] = mapped_column(nullable=False, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    available_hours_weekly: Mapped[float] = mapped_column(Float, default=40.0)

    # Skills stored as a comma-separated string for simplicity
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # One-to-many relationship with preferences
    preferences: Mapped[list["StaffShiftPreferenceModel"]] = relationship(
        "StaffShiftPreferenceModel",
        back_populates="nurse",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eagerly load preferences to avoid N+1 issues in async domain conversion
    )

    def to_domain(self) -> NurseProfile:
        """
        Converts the database model to the NurseProfile domain entity.
        """
        return NurseProfile(
            employee_id=self.employee_id,
            available_hours_weekly=self.available_hours_weekly,
            skills=self.skills,
            shift_custom_preferences=[p.to_domain() for p in self.preferences],
        )

    @classmethod
    def from_domain(
        cls,
        org_id: str,
        domain: NurseProfile,
    ) -> "NurseProfileModel":
        if domain.shift_custom_preferences:
            custom_preferences_ = [
                StaffShiftPreferenceModel.from_domain(domain.employee_id, p)
                for p in domain.shift_custom_preferences
            ]
        else:
            custom_preferences_ = []

        return cls(
            org_id=org_id,
            employee_id=domain.employee_id,
            available_hours_weekly=domain.available_hours_weekly,
            skills=domain.skills,
            preferences=custom_preferences_,
        )
