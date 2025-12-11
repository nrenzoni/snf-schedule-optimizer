from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from snf_schedule_optimizer.models import Schedule
from snf_schedule_optimizer.services.scheduling.interfaces import IScheduleRetriever
from snf_schedule_optimizer.sqlalchemy_models.schedule_assignment import (
    ScheduleAssignmentModel,
)


class SQLAlchemyScheduleRetriever(IScheduleRetriever):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_schedule(self, schedule_id: str, org_id: str) -> Schedule | None:
        """
        Fetches assignments from the DB and reconstructs the Domain Schedule object.
        """
        stmt = select(ScheduleAssignmentModel).where(
            ScheduleAssignmentModel.schedule_id == schedule_id,
            ScheduleAssignmentModel.org_id == org_id,
        )

        results = self.db_session.execute(stmt).scalars().all()

        if not results:
            return None

        # Map DB Rows -> Domain Object
        # Structure: dict[shift_id, list[employee_id]]
        assignments: dict[str, list[str]] = defaultdict(list)

        for row in results:
            assignments[str(row.shift_id)].append(str(row.employee_id))

        return Schedule(shift_assignments=assignments)
