import abc

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import NurseProfile, Shift
from snf_schedule_optimizer.sqlalchemy_models.nurse_profile import NurseProfileModel


class INurseRetriever(abc.ABC):
    @abc.abstractmethod
    async def get_nurses(
        self,
        shift: Shift,
    ) -> list[NurseProfile]:
        pass

    @abc.abstractmethod
    async def get_nurse(
        self,
        employee_id: str,
    ) -> NurseProfile | None:
        pass


class NurseRetrieverStaticListImpl(INurseRetriever):
    def __init__(
        self,
        nurses: list[NurseProfile],
    ):
        self.nurses = nurses
        self.nurse_dict = {n.employee_id: n for n in nurses}

    async def get_nurses(
        self,
        shift: Shift,
    ) -> list[NurseProfile]:
        # In a real implementation, filter nurses based on availability, skills, etc.
        return self.nurses

    async def get_nurse(self, employee_id: str) -> NurseProfile | None:
        return self.nurse_dict[employee_id]


class SQLNurseRetriever(INurseRetriever):
    """
    Asynchronous SQLAlchemy implementation of the INurseRetriever.
    Designed for use with async_session in an ASGI environment.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_nurses(self, shift: Shift) -> list[NurseProfile]:
        """
        Retrieves all active nurse profiles.
        In production, this would typically filter by facility_id or org_id from the shift.
        """
        stmt = select(NurseProfileModel)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_nurse(self, employee_id: str) -> NurseProfile | None:
        """
        Retrieves a specific nurse profile by employee ID.
        """
        stmt = select(NurseProfileModel).where(
            NurseProfileModel.employee_id == employee_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        return model.to_domain() if model else None
