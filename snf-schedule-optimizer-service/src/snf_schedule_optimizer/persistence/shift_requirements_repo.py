from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import Shift, ShiftSpecificRequirements
from snf_schedule_optimizer.services.scheduling.interfaces import (
    IShiftRequirementsRepo,
)
from snf_schedule_optimizer.sqlalchemy_models.shift_requirements import (
    ShiftRequirementsModel,
)


class SQLShiftRequirementsRepo(IShiftRequirementsRepo):
    """
    Adapter: SQLAlchemy implementation of the shift requirements port.
    Uses AsyncSession for non-blocking I/O.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_shift_requirements(
        self,
        shift: Shift,
    ) -> ShiftSpecificRequirements | None:
        """
        Retrieves staffing targets for a specific shift.
        Returns zeroed requirements if no record exists.
        """
        stmt = select(ShiftRequirementsModel).where(
            and_(
                ShiftRequirementsModel.org_id == shift.org_id,
                ShiftRequirementsModel.facility_id == shift.facility_id,
                ShiftRequirementsModel.shift_id == shift.shift_id,
            )
        )

        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return None

        return record.to_domain()
