from collections import defaultdict
from itertools import groupby
from typing import Dict, Iterable, List, Tuple
from uuid import uuid4

import pendulum
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from snf_schedule_optimizer.models import Shift, TimePunch, WorkedShiftSegment
from snf_schedule_optimizer.services.interfaces import IRawHistoryRetriever
from snf_schedule_optimizer.sqlalchemy_models.shift import ShiftModel
from snf_schedule_optimizer.sqlalchemy_models.time_punch_model import TimePunchModel

RawHistoryRecord = Tuple[str, Shift, List[TimePunch]]


class RawHistoryRetrieverStaticListImpl(IRawHistoryRetriever):
    """
    Concrete implementation that provides raw shift and punch data from a static
    list, filtered by employee ID and date range.
    """

    def __init__(self, records: List[RawHistoryRecord]):
        """
        Initializes with a list of pre-grouped shift and punch data.
        """
        self.shift_assignment_map: Dict[str, List[Tuple[Shift, List[TimePunch]]]] = defaultdict(list)
        for employee_id, shift, punches in records:
            self.shift_assignment_map[employee_id].append((shift, punches))

    def get_raw_inputs_for_period(
            self,
            employee_id: str,
            check_date: pendulum.DateTime,
    ) -> Dict[Shift, List[TimePunch]]:

        history_map: Dict[Shift, List[TimePunch]] = {}

        # Define the relevant period (8 days lookback, matching the Calculator's assumption)
        max_lookback_dt = check_date.subtract(days=8).start_of('day')

        if employee_id not in self.shift_assignment_map:
            return {}

        employee_history = self.shift_assignment_map[employee_id]

        for shift, punches in employee_history:
            # Filter: Check Date Range (shift ended before check_date and started within lookback)
            if shift.shift_end_dt <= check_date and shift.shift_start_dt >= max_lookback_dt:

                # Filter: Check Punches (Only include punches valid for the shift's context)
                # We assume the external system/API provides only relevant punches,
                # but we check the time bounds for safety.

                valid_punches = [
                    p for p in punches
                    if max_lookback_dt <= p.punch_time <= check_date
                ]

                if valid_punches:
                    history_map[shift] = valid_punches

        return history_map


class SQLARawHistoryRetriever(IRawHistoryRetriever):
    """
    Concrete implementation using SQLAlchemy to fetch raw Shifts and Punches
    via the direct FK from TimePunch to Shift.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_raw_inputs_for_period(
            self,
            employee_id: str,
            check_date: pendulum.DateTime,
    ) -> Dict[Shift, List[TimePunch]]:

        # 1. Define the Lookback Period
        # We look back enough to cover the max OT lookback (e.g., 7 days)
        max_lookback_dt = check_date.subtract(days=8).start_of('day')

        # 1. Query Punches and Eagerly Load Shifts
        # Fetch all time punches for the employee within the lookback window,
        # ensuring the linked shift template is loaded simultaneously.
        punch_stmt = select(TimePunchModel).options(
            # Eagerly load the Shift Template linked by TimePunchModel.shift_id
            joinedload(TimePunchModel.shift_template)
        ).where(
            and_(
                TimePunchModel.employee_id == employee_id,
                TimePunchModel.punch_time >= max_lookback_dt,
                TimePunchModel.punch_time <= check_date
            )
        ).order_by(TimePunchModel.punch_time)

        punch_models: Iterable[TimePunchModel] = self.db_session.execute(punch_stmt).scalars().all()

        if not punch_models:
            return {}

        # 2. Group Results by Shift Template

        placeholder_shift = self._get_placeholder_shift()

        # Helper to map and extract the Shift domain object
        def get_shift_domain(p: TimePunchModel) -> Shift:
            # Handle unassigned punches by creating a placeholder shift object
            if p.shift_template is None:
                return placeholder_shift

            # Map the template using the original helper
            return self._map_shift_to_domain(p.shift_template)

        history_map: Dict[Shift, List[TimePunch]] = {}

        # Grouping: Group all punch models by the ID of their associated Shift Template
        # We group by the shift template ID, even though the result is keyed by the Shift object.
        for shift_model_id, punch_group in groupby(punch_models, key=lambda p: p.shift_id):

            punch_list = list(punch_group)

            # Get the Shift Domain Object (either template or placeholder)
            shift_domain_object = get_shift_domain(punch_list[0])

            # Map all punches in the group to the domain object list
            punches_domain = [self._map_punch_model_to_domain(p) for p in punch_list]

            # Store result
            history_map[shift_domain_object] = punches_domain

        return history_map

    def _map_shift_to_domain(self, shift_model: ShiftModel) -> Shift:
        """Maps a SQLAlchemy Shift model to the application's Shift dataclass."""
        # We assume Shift only holds identity and basic time data for history purposes.
        return Shift(
            shift_id=str(shift_model.id),
            shift_start_dt=pendulum.instance(shift_model.shift_start_dt),
            shift_end_dt=pendulum.instance(shift_model.shift_end_dt),

            shift_number=int(shift_model.shift_number) if shift_model.shift_number is not None else 0,
            day_shift=shift_model.day_shift,

            day_of_week=pendulum.WeekDay(shift_model.day_of_week),

            timezone=pendulum.timezone(shift_model.timezone),
        )

    def _map_punch_model_to_domain(self, punch_model: TimePunchModel) -> TimePunch:
        """Maps a TimePunchModel to the application's TimePunch dataclass."""
        if punch_model.punch_time is None:
            raise ValueError(f"TimePunchModel {punch_model.id} missing critical punch_time.")

        return TimePunch(
            employee_id=punch_model.employee_id,
            # Pass non-Optional DateTime object
            punch_time=pendulum.instance(punch_model.punch_time),
            raw_punch_id=punch_model.raw_punch_id,
            punch_recorded_at=pendulum.instance(punch_model.punch_recorded_at)
            # All other Optional fields default to None/False in the dataclass.
        )

    def _get_placeholder_shift(self) -> Shift:
        # Create a generic shift object to hold raw, unassigned punches
        now = pendulum.now()
        return Shift(
            shift_id="UNASSIGNED",
            shift_start_dt=now.subtract(days=365).start_of('day'),
            shift_end_dt=now.add(days=1).end_of('day'),
            shift_number=99,
            day_shift=False,
            day_of_week=pendulum.SUNDAY,
            timezone=pendulum.timezone("UTC"),
        )
