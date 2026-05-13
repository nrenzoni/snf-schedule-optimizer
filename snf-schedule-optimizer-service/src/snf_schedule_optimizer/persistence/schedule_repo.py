from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete, func, select
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
from snf_schedule_optimizer.sqlalchemy_models.schedule_record import ScheduleRecordModel
from snf_schedule_optimizer.sqlalchemy_models.shift import ShiftModel


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

        schedule_record = await self.db_session.get(
            ScheduleRecordModel, schedule_lookup.schedule_id
        )

        return Schedule(
            org_id=schedule_lookup.org_id,
            facility_id=schedule_record.facility_id if schedule_record else None,
            schedule_id=schedule_lookup.schedule_id,
            schedule_version=schedule_record.version if schedule_record else 1,
            shift_assignments=assignments,
            start_date=schedule_record.start_date if schedule_record else None,
            end_date=schedule_record.end_date if schedule_record else None,
        )

    async def get_schedule_for_month(
        self,
        org_id: int,
        facility_id: int | None,
        start_date: str,
    ) -> Schedule | None:
        record_stmt = select(ScheduleRecordModel).where(
            ScheduleRecordModel.org_id == org_id,
            ScheduleRecordModel.start_date <= start_date,
            ScheduleRecordModel.end_date >= start_date,
        )
        if facility_id is not None:
            record_stmt = record_stmt.where(ScheduleRecordModel.facility_id == facility_id)
        record_stmt = record_stmt.order_by(
            ScheduleRecordModel.updated_at.desc(),
            ScheduleRecordModel.schedule_id.desc(),
        )
        schedule_record = (await self.db_session.scalars(record_stmt)).first()
        if schedule_record is None:
            return None

        stmt = select(ScheduleAssignmentModel).where(
            ScheduleAssignmentModel.org_id == org_id,
            ScheduleAssignmentModel.schedule_id == schedule_record.schedule_id,
        )
        results = (await self.db_session.scalars(stmt)).all()

        assignments: ShiftAssignmentsType = defaultdict(list)
        for row in results:
            assignments[ShiftKey(row.facility_id, row.shift_id)].append(row.employee_id)

        return Schedule(
            org_id=org_id,
            facility_id=schedule_record.facility_id,
            schedule_id=schedule_record.schedule_id,
            schedule_version=schedule_record.version,
            shift_assignments=assignments,
            start_date=schedule_record.start_date,
            end_date=schedule_record.end_date,
        )

    async def save_schedule(self, schedule: Schedule) -> None:
        if schedule.schedule_id is None:
            raise ValueError("schedule_id is required to persist a schedule")

        facility_ids = {shift_key.facility_id for shift_key in schedule.shift_assignments}
        facility_id = schedule.facility_id
        if facility_id is None:
            if len(facility_ids) != 1:
                raise ValueError("schedule.facility_id is required for persistence")
            facility_id = next(iter(facility_ids))

        shift_ids = [shift_key.shift_id for shift_key in schedule.shift_assignments]
        start_date = schedule.start_date or ""
        end_date = schedule.end_date or ""
        if shift_ids and (not start_date or not end_date):
            shift_stmt = select(ShiftModel).where(
                ShiftModel.org_id == schedule.org_id,
                ShiftModel.facility_id == facility_id,
                ShiftModel.id.in_(shift_ids),
            )
            shift_models = (await self.db_session.scalars(shift_stmt)).all()
            if shift_models:
                shift_dates = sorted(
                    shift.shift_start_dt.to_tz("America/New_York").date().format_common_iso()
                    for shift in shift_models
                )
                start_date = shift_dates[0]
                end_date = shift_dates[-1]

        existing_record = await self.db_session.get(ScheduleRecordModel, schedule.schedule_id)
        if existing_record is None:
            self.db_session.add(
                ScheduleRecordModel(
                    schedule_id=schedule.schedule_id,
                    org_id=schedule.org_id,
                    facility_id=facility_id,
                    start_date=start_date,
                    end_date=end_date,
                    version=schedule.schedule_version,
                )
            )
        else:
            existing_record.facility_id = facility_id
            existing_record.start_date = start_date
            existing_record.end_date = end_date
            existing_record.version = schedule.schedule_version

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

    async def next_schedule_id(self, org_id: int) -> int:
        stmt = select(func.max(ScheduleRecordModel.schedule_id)).where(
            ScheduleRecordModel.org_id == org_id
        )
        current_max = await self.db_session.scalar(stmt)
        if current_max is None:
            current_max = await self.db_session.scalar(
                select(func.max(ScheduleAssignmentModel.schedule_id)).where(
                    ScheduleAssignmentModel.org_id == org_id
                )
            )
        return (current_max or 0) + 1
