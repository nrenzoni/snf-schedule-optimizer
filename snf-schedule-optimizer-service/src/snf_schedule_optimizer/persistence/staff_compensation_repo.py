import whenever
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import StaffCompensationRecord
from snf_schedule_optimizer.services.hr.interfaces import IStaffCompensationRepo
from snf_schedule_optimizer.sqlalchemy_models.staff_compensation_model import (
    StaffCompensationModel,
)


class SQLStaffCompensationRepo(IStaffCompensationRepo):
    """
    Concrete implementation of the compensation service using SQLAlchemy.
    Retrieves the one valid rate record for a given date.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_record_for_date(
        self,
        employee_id: str,
        check_date: whenever.ZonedDateTime,
    ) -> StaffCompensationRecord | None:
        """
        Retrieves the StaffCompensationRecord whose validity period covers the check_date.
        """

        # Normalize the check date to a Python date object for database comparison
        check_date_for_db = check_date.date()

        # 1. Construct the Query: Find the record where the check date falls within the range.
        stmt = (
            select(StaffCompensationModel)
            .where(
                # Filter by the employee
                StaffCompensationModel.employee_id == employee_id,
                # Filter 1: Check date must be >= start date
                StaffCompensationModel.effective_start_date <= check_date_for_db,
                # Filter 2: Check date must be < end date (or end date must be NULL/future)
                # We use an OR clause to handle the open-ended record (NULL end_date)
                or_(
                    StaffCompensationModel.effective_end_date.is_(None),
                    StaffCompensationModel.effective_end_date > check_date_for_db,
                ),
            )
            .order_by(
                # Order by start date descending to help confirm the active record in case of overlap/tie
                StaffCompensationModel.effective_start_date.desc()
            )
            .limit(1)
        )

        # 2. Execute and Retrieve
        result: StaffCompensationModel | None = (
            await self.db_session.execute(stmt)
        ).scalar_one_or_none()

        if result is None:
            return None

        # 3. Map and Return
        return result.to_data()
