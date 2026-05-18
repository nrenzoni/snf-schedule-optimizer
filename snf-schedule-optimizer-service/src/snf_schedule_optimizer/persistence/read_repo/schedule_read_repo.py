"""Read-optimized repository for schedule queries."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models.read.schedule_views import (
    ScheduleDayView,
    ShiftAssignmentView,
)
from snf_schedule_optimizer.sqlalchemy_models.employee import EmployeeModel
from snf_schedule_optimizer.sqlalchemy_models.schedule_assignment import (
    ScheduleAssignmentModel,
)
from snf_schedule_optimizer.sqlalchemy_models.shift import ShiftModel


class ScheduleReadRepo:
    """Read-model repository using optimized JOIN queries."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_day_view(
        self, org_id: int, facility_id: int, date_str: str
    ) -> ScheduleDayView | None:
        """Single optimized query to get all assignments for a date."""
        pass

    async def get_shifts_for_date_range(
        self, org_id: int, facility_id: int, start_date: str, end_date: str
    ) -> Sequence[ShiftAssignmentView]:
        """Get all shift assignments for a date range in one query."""
        stmt = (
            select(
                ScheduleAssignmentModel,
                ShiftModel,
                EmployeeModel,
            )
            .join(
                ShiftModel,
                (ScheduleAssignmentModel.org_id == ShiftModel.org_id)
                & (ScheduleAssignmentModel.facility_id == ShiftModel.facility_id)
                & (ScheduleAssignmentModel.shift_id == ShiftModel.id),
            )
            .join(
                EmployeeModel,
                (ScheduleAssignmentModel.org_id == EmployeeModel.org_id)
                & (ScheduleAssignmentModel.employee_id == EmployeeModel.id),
            )
            .where(
                ShiftModel.org_id == org_id,
                ShiftModel.facility_id == facility_id,
                ShiftModel.shift_start_dt >= start_date,
                ShiftModel.shift_end_dt <= end_date,
            )
        )
        result = await self._session.execute(stmt)
        rows = result.unique().all()

        views: list[ShiftAssignmentView] = []
        for _assignment, shift, employee in rows:
            views.append(
                ShiftAssignmentView(
                    shift_id=shift.id,
                    facility_id=shift.facility_id,
                    nurse_id=employee.id,
                    nurse_name=employee.name,
                    role=employee.job_title,  # simplified mapping
                    unit_name=f"Unit {shift.unit_id or '?'}",
                    unit_id=shift.unit_id,
                    shift_start=shift.shift_start_dt,
                    shift_end=shift.shift_end_dt,
                    is_locked=False,
                    cost_cents=0,
                )
            )
        return views
