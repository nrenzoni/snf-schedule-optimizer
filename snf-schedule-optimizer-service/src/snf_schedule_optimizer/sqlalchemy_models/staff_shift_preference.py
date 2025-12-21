from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snf_schedule_optimizer.models import PreferenceType, StaffShiftPreference
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase
from snf_schedule_optimizer.sqlalchemy_models.nurse_profile import NurseProfileModel


class StaffShiftPreferenceModel(SQLABase):
    """
    SQLAlchemy model for individual nurse preferences (e.g., weekends off).
    """

    __tablename__ = "staff_shift_preference"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(32), nullable=False)

    preference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    specific_value: Mapped[str | None] = mapped_column(String(100))
    penalty_weight: Mapped[float] = mapped_column(Float, default=10.0)
    is_hard_block: Mapped[bool] = mapped_column(Boolean, default=False)

    nurse: Mapped[NurseProfileModel] = relationship(
        "NurseProfileModel", back_populates="preferences"
    )

    def to_domain(self) -> StaffShiftPreference:
        """
        Converts to the StaffShiftPreference value object.
        """
        return StaffShiftPreference(
            preference_type=PreferenceType(self.preference_type),
            specific_value=self.specific_value,
            penalty_weight=self.penalty_weight,
            is_hard_block=self.is_hard_block,
        )
