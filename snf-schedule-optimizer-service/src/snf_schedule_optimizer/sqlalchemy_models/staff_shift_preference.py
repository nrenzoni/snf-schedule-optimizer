from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from snf_schedule_optimizer.models import (
    EmployeeIdType,
    PreferenceType,
    StaffShiftPreference,
)
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase

if TYPE_CHECKING:
    from snf_schedule_optimizer.sqlalchemy_models.nurse_profile import NurseProfileModel


class StaffShiftPreferenceModel(SQLABase):
    """
    SQLAlchemy model for individual nurse preferences (e.g., weekends off).
    """

    __tablename__ = "staff_shift_preference"

    __table_args__ = (
        ForeignKeyConstraint(
            ("org_id", "employee_id"),
            ["nurse_profile.org_id", "nurse_profile.employee_id"],
            name="fk_staff_preference_nurse_profile",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(nullable=False)
    employee_id: Mapped[int] = mapped_column(nullable=False)

    preference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    specific_value: Mapped[str | None] = mapped_column(String(100))
    penalty_weight: Mapped[float] = mapped_column(Float, default=10.0)
    is_hard_block: Mapped[bool] = mapped_column(Boolean, default=False)

    nurse: Mapped["NurseProfileModel"] = relationship(
        "NurseProfileModel",
        back_populates="preferences",
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

    @staticmethod
    def from_domain(
        employee_id: EmployeeIdType,
        domain: StaffShiftPreference,
    ) -> "StaffShiftPreferenceModel":
        return StaffShiftPreferenceModel(
            employee_id=employee_id,
            preference_type=domain.preference_type.value,
            specific_value=domain.specific_value,
            penalty_weight=domain.penalty_weight,
            is_hard_block=domain.is_hard_block,
        )


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(StaffShiftPreferenceModel.__table__)
