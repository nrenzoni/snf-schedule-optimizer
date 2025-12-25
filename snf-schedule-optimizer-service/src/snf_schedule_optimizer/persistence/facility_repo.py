from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.domain.repositories import IFacilityRepo
from snf_schedule_optimizer.models import DomainPrimaryKeyType, FacilityConfig
from snf_schedule_optimizer.sqlalchemy_models.facility_config import FacilityConfigModel


class SQLFacilityRepo(IFacilityRepo):
    """
    SQLAlchemy implementation of IFacilityRepository.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_configs(
        self,
        org_id: DomainPrimaryKeyType,
        facility_ids: list[DomainPrimaryKeyType] | None = None,
    ) -> list[FacilityConfig]:
        """
        Retrieves configuration (including timezone) for facilities in an org.
        """
        stmt = select(FacilityConfigModel).where(FacilityConfigModel.org_id == org_id)

        if facility_ids:
            stmt = stmt.where(FacilityConfigModel.facility_id.in_(facility_ids))

        results = (await self.session.scalars(stmt)).all()

        return [row.to_domain() for row in results]

    async def get_all_facilities(self) -> list[FacilityConfig]:
        stmt = select(FacilityConfigModel)
        result = await self.session.scalars(stmt)
        models: Sequence[FacilityConfigModel] = result.all()
        return [m.to_domain() for m in models]

    async def save_config(self, config: FacilityConfig) -> None:
        """
        Saves or updates a FacilityConfig record.
        """
        model = FacilityConfigModel.from_domain(config)
        await self.session.merge(model)
