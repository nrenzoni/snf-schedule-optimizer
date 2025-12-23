from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import (
    Schedule,
    ShiftAssignmentsType,
    ShiftKey,
)
from snf_schedule_optimizer.services.scheduling.interfaces import (
    IScheduleRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.sqlalchemy_models.schedule_assignment import (
    ScheduleAssignmentModel,
)


class SQLScheduleRepo(IScheduleRepo):
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_schedule(
        self,
        schedule_lookup: ScheduleLookupKey,
    ) -> Schedule | None:
        """
        Fetches assignments from the DB and reconstructs the Domain Schedule object.
        """
        stmt = select(ScheduleAssignmentModel).where(
            ScheduleAssignmentModel.org_id == schedule_lookup.org_id,
            ScheduleAssignmentModel.schedule_id == schedule_lookup.schedule_id,
        )

        results: Sequence[ScheduleAssignmentModel] | None = (
            await self.db_session.scalars(stmt)
        ).all()

        if not results:
            return None

        # Map DB Rows -> Domain Object
        # Structure: dict[shift_id, list[employee_id]]
        assignments: ShiftAssignmentsType = defaultdict(list)

        for row in results:
            assignments[ShiftKey(row.facility_id, row.shift_id)].append(
                str(row.employee_id)
            )

        return Schedule(
            schedule_lookup.org_id,
            None,
            schedule_lookup.schedule_id,
            shift_assignments=assignments,
        )
