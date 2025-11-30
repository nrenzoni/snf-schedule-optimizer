import abc
from typing import Dict, List, Optional

import pendulum

from snf_schedule_optimizer.models import (
    Employee,
    LookbackPeriod,
    Shift,
    TimePunch,
    WorkedShiftSegment,
)
from snf_schedule_optimizer.services.payroll.calculations.overtime_calculation import (
    ThresholdOvertimeRule,
)


class IEmployeeWorkHistoryService(abc.ABC):
    """
    Retrieves and calculates a nurse's accumulated hours against a specific OT threshold.
    """

    @abc.abstractmethod
    def get_remaining_non_ot_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        ot_rules: List["ThresholdOvertimeRule"],
    ) -> Dict[LookbackPeriod, float]:
        """
        Calculates the minimum remaining non-OT hours based on all provided rules
        (daily and weekly).
        Returns a dictionary: {'daily': float, 'weekly': float}
        """
        pass

    @abc.abstractmethod
    def get_accumulated_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        history: Dict[Shift, List[WorkedShiftSegment]],
        threshold_hours: float,
        lookback_period: LookbackPeriod,
        work_period_start_day: Optional[int] = None,  # pendulum.DayOfWeek
        work_period_start_time: Optional[pendulum.Time] = None,
    ) -> float:
        """
        Calculates total non-OT hours accumulated by the employee
        within the defined work period (day/week) up to the current shift's start time.
        """
        pass

    @abc.abstractmethod
    def get_consecutive_days_worked(
        self,
        employee: Employee,
        current_shift: Shift,
        history: Dict[Shift, List[WorkedShiftSegment]],
        max_consecutive_days: int,
    ) -> List[pendulum.Date]:
        """
        Calculates the number of consecutive calendar days worked immediately
        leading up to the current shift's start date.
        Returns a list of pendulum.Date objects representing the consecutive days worked.
        """
        pass

    @abc.abstractmethod
    def get_processed_history_for_period(
        self,
        employee_id: str,
        up_to_check_date: pendulum.DateTime,
    ) -> Dict[Shift, List[WorkedShiftSegment]]:
        """
        Retrieves all previously processed shifts and their segments for the employee
        that fall within the relevant lookback period (e.g., the last 7 days/last 24 hours
        relative to the check_date).
        """
        pass


class IRawHistoryRetriever(abc.ABC):
    """Defines the contract for fetching raw, unprocessed historical inputs."""

    @abc.abstractmethod
    def get_raw_inputs_for_period(
        self,
        employee_id: str,
        check_date: pendulum.DateTime,
    ) -> Dict[Shift, List[TimePunch]]:
        """
        Retrieves all scheduled Shifts and their corresponding raw TimePunches
        for the period relevant to the check_date. (The structure ensures pairing
        occurs in the Reconciler.)
        """
        pass
