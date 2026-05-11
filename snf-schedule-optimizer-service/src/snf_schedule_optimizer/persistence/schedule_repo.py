from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IScheduleRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.models import (
    Schedule,
    ShiftAssignmentsType,
    ShiftKey,
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
            assignments[ShiftKey(row.facility_id, row.shift_id)].append(row.employee_id)

        return Schedule(
            schedule_lookup.org_id,
            None,
            schedule_lookup.schedule_id,
            shift_assignments=assignments,
        )

    async def get_schedule_for_month(
        self,
        org_id: int,
        facility_id: int | None,
        start_date: str,
    ) -> Schedule | None:
        stmt = select(ScheduleAssignmentModel).where(
            ScheduleAssignmentModel.org_id == org_id,
        )

        if facility_id is not None:
            stmt = stmt.where(ScheduleAssignmentModel.facility_id == facility_id)

        stmt = stmt.order_by(ScheduleAssignmentModel.schedule_id)
        results = (await self.db_session.scalars(stmt)).all()

        if not results:
            return None

        schedule_id = results[0].schedule_id
        assignments: ShiftAssignmentsType = defaultdict(list)
        for row in results:
            if row.schedule_id != schedule_id:
                break
            assignments[ShiftKey(row.facility_id, row.shift_id)].append(row.employee_id)

        return Schedule(
            org_id=org_id,
            facility_id=facility_id,
            schedule_id=schedule_id,
            shift_assignments=assignments,
        )

    async def save_schedule(self, schedule: Schedule) -> None:
        if schedule.schedule_id is None:
            raise ValueError("schedule_id is required to persist a schedule")

        await self.db_session.execute(
            delete(ScheduleAssignmentModel).where(
                ScheduleAssignmentModel.org_id == schedule.org_id,
                ScheduleAssignmentModel.schedule_id == schedule.schedule_id,
            )
        )

        assignment_id = 1
        for shift_key, employee_ids in schedule.shift_assignments.items():
            for employee_id in employee_ids:
                self.db_session.add(
                    ScheduleAssignmentModel(
                        schedule_id=schedule.schedule_id,
                        assignment_id=assignment_id,
                        org_id=schedule.org_id,
                        facility_id=shift_key.facility_id,
                        shift_id=shift_key.shift_id,
                        employee_id=employee_id,
                    )
                )
                assignment_id += 1
