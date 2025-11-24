import abc
import pendulum
import math
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
import datetime

from snf_schedule_optimizer.models import PunchType
from snf_schedule_optimizer.services.interfaces import IFacilityRulesService
from snf_schedule_optimizer.sqlalchemy_models.facility_rules_config import FacilityRulesConfigModel


class SQLAFacilityRulesService(IFacilityRulesService):
    """
    Applies rules loaded dynamically from the database using SQLAlchemy.
    """

    def __init__(self, db_session: Session, facility_id: int):
        self.db_session = db_session
        self.facility_id = facility_id
        # Load rules eagerly upon instantiation
        self.rules_config = self._load_rules_config()
        self.rounding_unit_minutes = self.rules_config.get('rounding_unit_minutes', 6)

    def apply_rounding(self, raw_time: pendulum.DateTime, punch_type: PunchType) -> pendulum.DateTime:
        """Applies the nearest-interval rounding rule."""
        # For simplicity, we apply standard nearest-interval rounding.
        return self._round_time(raw_time)

    def _load_rules_config(self) -> Dict[str, Any]:
        """
        Fetches the active FacilityRulesConfig from the database.
        """
        # Fetch the most recent active configuration for the facility
        stmt = select(FacilityRulesConfigModel).where(
            FacilityRulesConfigModel.facility_id == self.facility_id
            # NOTE: Add date filtering here if the config is versioned (e.g., current date between effective_date and expiration_date)
        ).order_by(
            # Assuming the highest ID/most recent is the active one if no date filtering
            FacilityRulesConfigModel.id.desc()
        ).limit(1)

        record = self.db_session.execute(stmt).scalar_one_or_none()

        if not record:
            raise ValueError(f"CRITICAL: No active facility rules found for facility ID {self.facility_id}")

        # Map the ORM record to a simple dictionary for easy internal access
        return {
            "rounding_unit_minutes"         : record.rounding_unit_minutes,
            "meal_deduction_threshold_hours": record.meal_deduction_threshold_hours,
            "meal_deduction_duration_hours" : record.meal_deduction_duration_hours,
            "meal_is_mandatory"             : record.meal_is_mandatory
        }

    def _round_time(self, dt: pendulum.DateTime) -> pendulum.DateTime:
        """Helper to apply the rounding logic to the nearest configured unit."""

        unit = self.rounding_unit_minutes

        # Calculate total minutes since midnight
        minutes_since_midnight = dt.hour * 60 + dt.minute + dt.second / 60.0

        # Calculate the closest multiple of the rounding unit
        rounded_minutes = round(minutes_since_midnight / unit) * unit

        # Convert back to hours, minutes, seconds
        new_hour = int(rounded_minutes // 60)
        new_minute = int(rounded_minutes % 60)

        # Use pendulum's set() method, which handles crossing midnight correctly
        return dt.set(hour=new_hour, minute=new_minute, second=0, microsecond=0)

