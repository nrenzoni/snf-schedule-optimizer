from __future__ import annotations

import abc
from typing import TYPE_CHECKING

import whenever

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    EmployeeIdType,
    LookbackPeriod,
    Shift,
    ShiftKey,
    TimePunch,
    WorkedShiftSegment,
)

if TYPE_CHECKING:
    from snf_schedule_optimizer.domain.payroll.calculations.overtime_calculation import (
        ThresholdOvertimeRule,
    )


class IEmployeeWorkHistoryService(abc.ABC):
    """
    Retrieves and calculates a nurse's accumulated hours against a specific OT threshold.
    """

    @abc.abstractmethod
    async def get_remaining_non_ot_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        ot_rules: list[ThresholdOvertimeRule],
    ) -> dict[LookbackPeriod, float]:
        """
        Calculates the minimum remaining non-OT hours based on all provided rules
        (daily and weekly).
        Returns a dictionary: {'daily': float, 'weekly': float}
        """
        pass

    @abc.abstractmethod
    async def get_accumulated_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        history: dict[ShiftKey, list[WorkedShiftSegment]],
        threshold_hours: float,
        lookback_period: LookbackPeriod,
        work_period_start_day: whenever.Weekday | None = None,  # pendulum.DayOfWeek
        work_period_start_time: whenever.Time | None = None,
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
        history: dict[Shift, list[WorkedShiftSegment]],
        max_consecutive_days: int,
    ) -> list[whenever.Date]:
        """
        Calculates the number of consecutive calendar days worked immediately
        leading up to the current shift's start date.
        Returns a list of whenever.Date objects representing the consecutive days worked.
        """
        pass

    @abc.abstractmethod
    async def get_processed_history_for_period(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: EmployeeIdType,
        check_date: whenever.Instant,
        facility_id: int | None = None,
    ) -> dict[ShiftKey, list[WorkedShiftSegment]]:
        """
        Retrieves all previously processed shifts and their segments for the employee
        that fall within the relevant lookback period (e.g., the last 7 days/last 24 hours
        relative to the check_date).
        """
        pass


class IRawHistoryRepo(abc.ABC):
    """Defines the contract for fetching raw, unprocessed historical inputs."""

    @abc.abstractmethod
    async def get_raw_inputs_for_period(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: EmployeeIdType,
        check_date: whenever.Instant,
        facility_timezones: dict[DomainPrimaryKeyType, str],
        facility_id: int | None = None,
    ) -> dict[ShiftKey, list[TimePunch]]:
        """
        Retrieves all scheduled Shifts and their corresponding raw TimePunches
        for the period relevant to the check_date. (The structure ensures pairing
        occurs in the Reconciler.)
        """
        pass
