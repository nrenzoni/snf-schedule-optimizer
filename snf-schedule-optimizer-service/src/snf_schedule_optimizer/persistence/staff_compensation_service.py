from sqlalchemy.orm import Session
from sqlalchemy import select, or_
import pendulum
from typing import Dict, List, Optional

from snf_schedule_optimizer.models import StaffCompensationRecord
from snf_schedule_optimizer.services.interfaces import IStaffCompensationService
from snf_schedule_optimizer.sqlalchemy_models.staff_compensation_model import (
    StaffCompensationModel,
)


class StaffCompensationServiceStaticListImpl(IStaffCompensationService):
    """
    Concrete implementation of the compensation service that uses a static,
    in-memory list of records (ideal for unit and integration testing).
    """

    def __init__(self, records: List[StaffCompensationRecord]):
        """
        Initializes the service with a list of historical compensation records.
        """
        # Group records by employee ID for faster lookup
        self.employee_records: Dict[str, List[StaffCompensationRecord]] = {}

        for record in records:
            if record.employee_id not in self.employee_records:
                self.employee_records[record.employee_id] = []

            self.employee_records[record.employee_id].append(record)

        # Ensure records for each employee are sorted by start date descending
        # This helps when looking for the most recent valid record.
        for employee_id in self.employee_records:
            self.employee_records[employee_id].sort(
                key=lambda r: r.effective_start_date, reverse=True
            )

    def get_record_for_date(
        self,
        employee_id: str,
        check_date: pendulum.DateTime,
    ) -> Optional[StaffCompensationRecord]:
        """
        Retrieves the one StaffCompensationRecord whose validity period
        covers the check_date.
        """

        if employee_id not in self.employee_records:
            return None

        # Check date should be compared to simple date for consistency with database storage
        check_date_date = check_date.date()

        for record in self.employee_records[employee_id]:
            # Check 1: Must be effective on or before the check date
            is_start_valid = record.effective_start_date <= check_date_date

            # Check 2: Must not be expired before the check date
            is_end_valid = (
                record.effective_end_date is None
                or record.effective_end_date > check_date_date
            )

            if is_start_valid and is_end_valid:
                return record

        return None


class SQLAStaffCompensationService(IStaffCompensationService):
    """
    Concrete implementation of the compensation service using SQLAlchemy.
    Retrieves the one valid rate record for a given date.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_record_for_date(
        self,
        employee_id: str,
        check_date: pendulum.DateTime,
    ) -> Optional[StaffCompensationRecord]:
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
        result = self.db_session.execute(stmt).scalar_one_or_none()

        if result is None:
            return None

        # 3. Map and Return
        return self._map_db_record_to_dataclass(result)

    def _map_db_record_to_dataclass(
        self,
        record: StaffCompensationModel,
    ) -> StaffCompensationRecord:
        """Translates the SQLAlchemy ORM object into the application dataclass."""

        # Note: We use cast(float, ...) for safety as the DB stores NUMERIC/Float
        return StaffCompensationRecord(
            employee_id=record.employee_id,
            base_rate_effective=record.base_rate_effective,
            ot_multiplier=record.ot_multiplier,
            is_agency=record.is_agency,
            # Map datetime.date from DB to pendulum.DateTime
            effective_start_date=pendulum.instance(record.effective_start_date),
            effective_end_date=pendulum.instance(record.effective_end_date)
            if record.effective_end_date
            else None,
            union_contract_id=record.union_contract_id,
            pay_grade_or_step=record.pay_grade_or_step,
        )
