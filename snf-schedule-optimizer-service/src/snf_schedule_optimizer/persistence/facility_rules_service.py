import pendulum
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from snf_schedule_optimizer.models import (
    EmployeeTimeSettings,
    MealDeductionRules,
    PunchType,
    RoundingType,
    SplitDayType,
)
from snf_schedule_optimizer.services.interfaces import IFacilityRulesService
from snf_schedule_optimizer.sqlalchemy_models.facility_rules_config import (
    FacilityRulesConfigModel,
)
from snf_schedule_optimizer.utils.time_utils import TimeRoundingUtility


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
            is_mandatory=True,
        )

    def apply_rounding(
        self,
        raw_time: pendulum.DateTime,
        punch_type: PunchType,
    ) -> pendulum.DateTime:
        """
        Applies a standard nearest-interval rounding (e.g., 6-minute rule).
        """
        return TimeRoundingUtility.round_to_nearest_unit(
            raw_time, self.DEFAULT_ROUNDING_UNIT
        )

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
            split_day_day_type=SplitDayType.CURRENT,
            rounding_type=RoundingType.NEAREST,
        )

    def get_meal_deduction_rules(
        self, check_dt: pendulum.DateTime
    ) -> Optional["MealDeductionRules"]:
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
        self.rounding_unit_minutes = self.rules_config.get("rounding_unit_minutes", 6)

    def apply_rounding(
        self, raw_time: pendulum.DateTime, punch_type: PunchType
    ) -> pendulum.DateTime:
        """Applies the nearest-interval rounding rule."""
        # For simplicity, we apply standard nearest-interval rounding.
        return TimeRoundingUtility.round_to_nearest_unit(
            raw_time, self.rounding_unit_minutes
        )

    def get_time_settings(
        self, employee_id: str, check_dt: pendulum.DateTime
    ) -> EmployeeTimeSettings:
        raise NotImplementedError()

    def get_meal_deduction_rules(
        self, check_dt: pendulum.DateTime
    ) -> Optional[MealDeductionRules]:
        raise NotImplementedError()

    def _load_rules_config(self) -> Dict[str, Any]:
        """
        Fetches the active FacilityRulesConfig from the database.
        """
        # Fetch the most recent active configuration for the facility
        stmt = (
            select(FacilityRulesConfigModel)
            .where(
                FacilityRulesConfigModel.facility_id == self.facility_id
                # NOTE: Add date filtering here if the config is versioned (e.g., current date between effective_date and expiration_date)
            )
            .order_by(
                # Assuming the highest ID/most recent is the active one if no date filtering
                FacilityRulesConfigModel.id.desc()
            )
            .limit(1)
        )

        record = self.db_session.execute(stmt).scalar_one_or_none()

        if not record:
            raise ValueError(
                f"CRITICAL: No active facility rules found for facility ID {self.facility_id}"
            )

        # Map the ORM record to a simple dictionary for easy internal access
        return {
            "rounding_unit_minutes": record.rounding_unit_minutes,
            "meal_deduction_threshold_hours": record.meal_deduction_threshold_hours,
            "meal_deduction_duration_hours": record.meal_deduction_duration_hours,
            "meal_is_mandatory": record.meal_is_mandatory,
        }
