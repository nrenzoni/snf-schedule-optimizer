import abc

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    NurseProfile,
    Shift,
)
from snf_schedule_optimizer.sqlalchemy_models.nurse_profile import NurseProfileModel


class INurseRepo(abc.ABC):
    @abc.abstractmethod
    async def get_nurses(
        self,
        shift: Shift,
    ) -> list[NurseProfile]:
        pass

    @abc.abstractmethod
    async def get_nurse(
        self,
        employee_id: DomainPrimaryKeyType,
    ) -> NurseProfile | None:
        pass

    @abc.abstractmethod
    async def save_nurse_profile(
        self,
        org_id: DomainPrimaryKeyType,
        nurse: NurseProfile,
    ) -> None:
        """Persists a domain NurseProfile and its associated preferences."""
        pass


class SQLNurseRepo(INurseRepo):
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
        stmt = select(NurseProfileModel).where(NurseProfileModel.org_id == shift.org_id)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        shift_duration = shift.duration_hours
        return [
            model.to_domain()
            for model in models
            if model.available_hours_weekly >= shift_duration
        ]

    async def get_nurse(self, employee_id: DomainPrimaryKeyType) -> NurseProfile | None:
        """
        Retrieves a specific nurse profile by employee ID.
        """
        stmt = select(NurseProfileModel).where(
            NurseProfileModel.employee_id == employee_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        return model.to_domain() if model else None

    async def save_nurse_profile(
        self,
        org_id: DomainPrimaryKeyType,
        nurse: NurseProfile,
    ) -> None:
        """
        Persists a domain NurseProfile and its associated preferences.
        """
        model = NurseProfileModel.from_domain(org_id, nurse)
        await self.session.merge(model)
