import abc
import pendulum
import math
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
import datetime

from snf_schedule_optimizer.models import EmployeeTimeSettings, MealDeductionRules, PunchType
from snf_schedule_optimizer.services.interfaces import IFacilityRulesService
from snf_schedule_optimizer.sqlalchemy_models.facility_rules_config import FacilityRulesConfigModel


class FacilityRulesServiceStaticListImpl(IFacilityRulesService):
    """
    Concrete implementation providing static, hardcoded payroll rules for testing
    the Shift Reconciler and other services.
    """

    def __init__(self) -> None:
        # Hardcode the essential parameters for internal use
        self.DEFAULT_ROUNDING_UNIT = 6
        self.DEFAULT_PAIRING_THRESHOLD = pendulum.duration(hours=10)
        self.DEFAULT_SPLIT_TIME = pendulum.time(3, 0, 0)
        self.DEFAULT_GRACE_WINDOW = pendulum.duration(minutes=15)

        # Instantiate the deduction rules once
        self.default_meal_rules = MealDeductionRules(
            meal_threshold_hours=6.0,
            meal_duration_hours=0.5,  # 30 minutes
            is_mandatory=True
        )

    def apply_rounding(self, raw_time: pendulum.DateTime, punch_type: 'PunchType') -> pendulum.DateTime:
        """
        Applies a standard nearest-interval rounding (e.g., 6-minute rule).
        """
        unit = self.DEFAULT_ROUNDING_UNIT

        # Calculate total minutes since midnight
        minutes_since_midnight = raw_time.hour * 60 + raw_time.minute + raw_time.second / 60.0

        # Round to the nearest multiple of the unit
        rounded_minutes = round(minutes_since_midnight / unit) * unit

        new_hour = int(rounded_minutes // 60)
        new_minute = int(rounded_minutes % 60)

        # Return the new DateTime object, letting pendulum handle carryover (e.g., 23:58 rounds to 00:00 next day)
        return raw_time.set(hour=new_hour, minute=new_minute, second=0, microsecond=0)

    def get_time_settings(
            self,
            employee_id: str,
            check_dt: pendulum.DateTime,
    ) -> EmployeeTimeSettings:
        """
        Retrieves hardcoded time settings, ignoring employee_id and date for simplicity.
        """
        # In production, this would filter by union contract/facility rules active on check_dt.
        return EmployeeTimeSettings(
            pairing_threshold=self.DEFAULT_PAIRING_THRESHOLD,
            split_day_threshold_time=self.DEFAULT_SPLIT_TIME,
            shift_separator_time=self.DEFAULT_SPLIT_TIME,  # Using the split time as separator for simplicity
            shift_grace_window=self.DEFAULT_GRACE_WINDOW,
            rounding_unit_minutes=self.DEFAULT_ROUNDING_UNIT,
        )

    def get_meal_deduction_rules(self, check_dt: pendulum.DateTime) -> Optional['MealDeductionRules']:
        """
        Retrieves the standard 6-hour threshold/30-minute mandatory deduction rules.
        """
        # In production, this would check state/federal laws and return the applicable rule.
        return self.default_meal_rules


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

    def get_time_settings(self, employee_id: str, check_dt: pendulum.DateTime) -> EmployeeTimeSettings:
        raise NotImplementedError()

    def get_meal_deduction_rules(self, check_dt: pendulum.DateTime) -> Optional[MealDeductionRules]:
        raise NotImplementedError()

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
