import itertools
from collections import defaultdict
from collections.abc import Iterable

import whenever
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from snf_schedule_optimizer.domain.timekeeping.interfaces import IRawHistoryRepo
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Shift,
    ShiftKey,
    TimePunch,
)
from snf_schedule_optimizer.sqlalchemy_models.time_punch_model import TimePunchModel

RawHistoryRecord = tuple[DomainPrimaryKeyType, Shift, list[TimePunch]]


class FakeRawHistoryRepo(IRawHistoryRepo):
    """
    Concrete implementation that provides raw shift and punch data from a static
    list, filtered by employee ID and date range.
    """

    def __init__(self, records: list[RawHistoryRecord]):
        """
        Initializes with a list of pre-grouped shift and punch data.
        """
        self.shift_assignment_map: dict[
            DomainPrimaryKeyType, list[tuple[Shift, list[TimePunch]]]
        ] = defaultdict(list)
        for employee_id, shift, punches in records:
            self.shift_assignment_map[employee_id].append((shift, punches))

    async def get_raw_inputs_for_period(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        check_date: whenever.Instant,
        facility_timezones: dict[DomainPrimaryKeyType, str],
        facility_id: DomainPrimaryKeyType | None = None,
    ) -> dict[ShiftKey, list[TimePunch]]:
        if employee_id not in self.shift_assignment_map:
            return {}

        history_map: dict[ShiftKey, list[TimePunch]] = {}

        # Define the relevant period (8 days lookback, matching the Calculator's assumption)
        max_lookback_dt = check_date.subtract(hours=8 * 24)

        employee_history = self.shift_assignment_map[employee_id]

        for shift, punches in employee_history:
            # Filter: Check Date Range (shift ended before check_date and started within lookback)
            if (
                shift.shift_end_dt <= check_date
                and shift.shift_start_dt >= max_lookback_dt
            ):
                # Filter: Check Punches (Only include punches valid for the shift's context)
                # We assume the external system/API provides only relevant punches,
                # but we check the time bounds for safety.

                valid_punches = [
                    p for p in punches if max_lookback_dt <= p.punch_time <= check_date
                ]

                if valid_punches:
                    history_map[shift.shift_key] = valid_punches

        return history_map


class SQLRawHistoryRepo(IRawHistoryRepo):
    """
    Concrete implementation using SQLAlchemy to fetch raw Shifts and Punches
    via the direct FK from TimePunch to Shift.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_raw_inputs_for_period(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        check_date: whenever.Instant,
        facility_timezones: dict[DomainPrimaryKeyType, str],
        facility_id: DomainPrimaryKeyType | None = None,
    ) -> dict[ShiftKey, list[TimePunch]]:
        # 1. Define the Lookback Period
        # We look back enough to cover the max OT lookback (e.g., 7 days)
        max_lookback_dt = check_date.subtract(hours=24 * 8)

        conditions = [
            TimePunchModel.org_id == org_id,
            TimePunchModel.employee_id == employee_id,
            TimePunchModel.shift_id.isnot(None),
            TimePunchModel.punch_time >= max_lookback_dt,
            TimePunchModel.punch_time <= check_date,
        ]

        if facility_id:
            conditions.append(TimePunchModel.facility_id == facility_id)

        punch_stmt = (
            select(TimePunchModel)
            .options(joinedload(TimePunchModel.shift_template))
            .where(and_(*conditions))
            .order_by(TimePunchModel.shift_id, TimePunchModel.punch_time)
        )

        punch_models: Iterable[TimePunchModel] = (
            await self.db_session.scalars(punch_stmt)
        ).all()

        if not punch_models:
            return {}

        # 2. Group Results by Shift Template

        # placeholder_shift = self._get_placeholder_shift()

        # # Helper to map and extract the Shift domain object
        # def get_shift_domain(p: TimePunchModel) -> Shift:
        #     # Handle unassigned punches by creating a placeholder shift object
        #     if p.shift_template is None:
        #         return placeholder_shift
        #
        #     # Map the template using the original helper
        #     return self._map_shift_to_domain(p.shift_template)

        history_map: dict[ShiftKey, list[TimePunch]] = {}

        # Grouping: Group all punch models by the ID of their associated Shift Template
        # We group by the shift template ID, even though the result is keyed by the Shift object.
        for shift_id, punch_group in itertools.groupby(
            punch_models, key=lambda p: p.shift_id
        ):
            # Since we filtered IS NOT NONE in SQL, strict casting to str is safe here.
            current_shift_id = shift_id
            punch_list = list(punch_group)

            actual_facility_id = punch_list[0].facility_id

            # Since we grouped by shift_id, all punches here share the same shift
            shift_domain_object = ShiftKey(
                facility_id=actual_facility_id,
                shift_id=current_shift_id,
            )

            facility_tz = facility_timezones.get(actual_facility_id)
            if not facility_tz:
                raise ValueError(
                    f"Timezone not found for facility_id: {actual_facility_id}"
                )

            # Map all punches in the group to the domain object list
            punches_domain = [
                self._map_punch_model_to_domain(p, facility_tz) for p in punch_list
            ]

            # Store result
            history_map[shift_domain_object] = punches_domain

        return history_map

    # def _map_shift_to_domain(
    #     self,
    #     shift_model: ShiftModel,
    #     tz: str,
    # ) -> Shift:
    #     """Maps a SQLAlchemy Shift model to the application's Shift dataclass."""
    #     # We assume Shift only holds identity and basic time data for history purposes.
    #     return Shift(
    #         org_id=shift_model.org_id,
    #         shift_key=ShiftKey(
    #             shift_model.facility_id,
    #             shift_model.shift_id,
    #         ),
    #         shift_start_dt=instant_to_zoned(shift_model.shift_start_dt, tz),
    #         shift_end_dt=instant_to_zoned(shift_model.shift_end_dt, tz),
    #         shift_number=int(shift_model.shift_number)
    #         if shift_model.shift_number is not None
    #         else 0,
    #         day_shift=shift_model.day_shift,
    #         day_of_week=whenever.Weekday(shift_model.day_of_week),
    #         tz=shift_model.timezone,
    #     )

    def _map_punch_model_to_domain(
        self, punch_model: TimePunchModel, tz: str
    ) -> TimePunch:
        """Maps a TimePunchModel to the application's TimePunch dataclass."""
        if punch_model.punch_time is None:
            raise ValueError(
                f"TimePunchModel {punch_model.id} missing critical punch_time."
            )

        return TimePunch(
            employee_id=punch_model.employee_id,
            # Pass non-Optional DateTime object
            punch_time=punch_model.punch_time.to_tz(tz),
            raw_punch_id=punch_model.raw_punch_id,
            punch_recorded_at=whenever.Instant.from_py_datetime(
                punch_model.punch_recorded_at
            ),
            # All other Optional fields default to None/False in the dataclass.
        )

    # def _get_placeholder_shift(self) -> Shift:
    #     # Create a generic shift object to hold raw, unassigned punches
    #     now = whenever.Instant.now()
    #     return Shift(
    #         org_id="UNKNOWN",
    #         shift_key=ShiftKey(
    #             facility_id="UNKNOWN",
    #             shift_id="UNASSIGNED",
    #         ),
    #         shift_start_dt=now.subtract(days=365).to_tz().start_of("day"),
    #         shift_end_dt=now.add(days=1).end_of("day"),
    #         shift_number=99,
    #         day_shift=False,
    #         day_of_week=whenever.SUNDAY,
    #         tz="UTC",
    #     )
