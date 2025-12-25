import whenever
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.models import ResidentAcuity
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase
from snf_schedule_optimizer.utils.sqlalchemy_types.whenever_types import InstantType


class ResidentAcuityModel(SQLABase):
    """
    SQLAlchemy model representing the 'resident_acuity' table.
    Captures daily snapshots of resident demand.
    """

    __tablename__ = "resident_acuity"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    resident_id: Mapped[int] = mapped_column(index=True, nullable=False)

    census_day: Mapped[whenever.Instant] = mapped_column(InstantType, primary_key=True)

    unit_id: Mapped[int] = mapped_column(index=True, nullable=False)
    pt_score_gg: Mapped[int] = mapped_column(Integer, default=0)
    nta_score: Mapped[int] = mapped_column(Integer, default=0)
    clinical_category: Mapped[str] = mapped_column(String(100), nullable=False)

    def to_domain(self, tz: str) -> ResidentAcuity:
        """Converts database record to domain entity."""
        return ResidentAcuity(
            resident_id=self.resident_id,
            unit_id=self.unit_id,
            census_day=self.census_day.to_tz(tz),
            pt_score_gg=int(self.pt_score_gg),
            nta_score=int(self.nta_score),
            clinical_category=str(self.clinical_category),
        )
