from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import FacilityConfig
from snf_schedule_optimizer.services.repositories import IFacilityRetriever
from snf_schedule_optimizer.sqlalchemy_models.facility_config import FacilityConfigModel


class SQLFacilityRetriever(IFacilityRetriever):
    """
    SQLAlchemy implementation of IFacilityRepository.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_configs(
        self,
        org_id: str,
        facility_ids: list[str] | None = None,
    ) -> list[FacilityConfig]:
        """
        Retrieves configuration (including timezone) for facilities in an org.
        """
        stmt = select(FacilityConfigModel).where(FacilityConfigModel.org_id == org_id)

        if facility_ids:
            stmt = stmt.where(FacilityConfigModel.facility_id.in_(facility_ids))

        results = (await self.session.scalars(stmt)).all()

        return [row.to_domain() for row in results]
