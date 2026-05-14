from collections.abc import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import ResidentAcuity, Shift
from snf_schedule_optimizer.resident_acuity_repo import (
    IResidentAcuityPerShiftRepo,
)
from snf_schedule_optimizer.sqlalchemy_models.resident_acuity import ResidentAcuityModel


class SQLResidentAcuityPerShiftRepo(IResidentAcuityPerShiftRepo):
    """
    Adapter: Fetches the resident census for the day of the shift.
    Filters by org, facility, and the date of the shift.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_resident_acuity_list(self, shift: Shift) -> list[ResidentAcuity]:
        """
        Retrieves all resident acuity records for the day the shift begins.
        """
        # We look for census records matching the date of the shift start

        # Note: Depending on the database type, we might need a cast or between check
        # for ZonedDateTime comparison. Here we assume exact day match at midnight.
        stmt = select(ResidentAcuityModel).where(
            and_(
                ResidentAcuityModel.org_id == shift.org_id,
                ResidentAcuityModel.facility_id == shift.facility_id,
                ResidentAcuityModel.unit_id == shift.unit_id,
                # Simple logic: records for the shift's calendar day
                ResidentAcuityModel.census_day >= shift.shift_start_dt.start_of_day(),
                ResidentAcuityModel.census_day < shift.shift_start_dt.start_of_day().add(days=1),
            )
        )

        result = await self.db_session.execute(stmt)
        records: Sequence[ResidentAcuityModel] = result.scalars().all()

        tz = shift.shift_start_dt.tz

        return [r.to_domain(tz) for r in records]
