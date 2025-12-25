from sqlalchemy import Float
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.models import ShiftSpecificRequirements
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class ShiftRequirementsModel(SQLABase):
    """
    SQLAlchemy model representing the 'shift_requirements' table.
    Stores HPRD targets per shift.
    """

    __tablename__ = "shift_requirements"

    # Composite Primary Key mapping to the Shift identity
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    shift_id: Mapped[int] = mapped_column(index=True, nullable=False)

    target_hprd_rn: Mapped[float] = mapped_column(Float, default=0.0)
    target_hprd_cna: Mapped[float] = mapped_column(Float, default=0.0)
    target_total_hprd: Mapped[float] = mapped_column(Float, default=0.0)

    def to_domain(self) -> ShiftSpecificRequirements:
        """Maps the ORM model to the domain dataclass."""
        return ShiftSpecificRequirements(
            target_hprd_rn=float(self.target_hprd_rn),
            target_hprd_cna=float(self.target_hprd_cna),
            target_total_hprd=float(self.target_total_hprd),
        )
