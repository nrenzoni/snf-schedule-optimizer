import abc
from enum import StrEnum
from typing import Dict, List, Optional

import pendulum
from typing_extensions import TYPE_CHECKING

from snf_schedule_optimizer.models import (
    Differential, DifferentialDateInterval, Employee,
    NurseProfile,
    OvertimeInterval,
    Shift, ShiftSpecificRequirements, StaffCompensationRecord, TimePunch, WorkedShiftSegment, WorkedTimeBlock,
    EmployeeTimeSettings,
    MealDeductionRules
)
from snf_schedule_optimizer.models.constraints import LookbackPeriod, PunchType

if TYPE_CHECKING:
    from snf_schedule_optimizer.services.calculations.overtime_calculation import ThresholdOvertimeRule


class ICertificationService(abc.ABC):
    @abc.abstractmethod
    def is_certification_active(
            self,
            employee_id: str,
            certification_name: str,
            check_date: pendulum.DateTime,
    ) -> bool:
        """Checks if the named certification is valid/unexpired on the check_date."""
        pass


class IOvertimeRuleRetrieverService(abc.ABC):
    """
    Defines the contract for fetching IOvertimeRule objects applicable to a specific context.
    """

    @abc.abstractmethod
    def get_applicable_rules(
            self,
            employee: Employee,
            shift: Shift,
    ) -> List['IOvertimeRule']:
        """
        Retrieves all active and eligible IOvertimeRule objects for the given
        employee and shift, often factoring in union/contract ID.
        """
        pass


class IEmployeeWorkHistoryService(abc.ABC):
    """
    Retrieves and calculates a nurse's accumulated hours against a specific OT threshold.
    """

    @abc.abstractmethod
    def get_remaining_non_ot_hours(
            self,
            employee: Employee,
            current_shift: Shift,
            ot_rules: List['ThresholdOvertimeRule'],
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


class IOvertimeCalculator(abc.ABC):
    """Determines which hours of a shift are subject to an OT multiplier."""

    @abc.abstractmethod
    def get_overtime_intervals(
            self,
            shift: Shift,
            employee: Employee,
            work_shift_history: Dict[Shift, List[WorkedShiftSegment]],
            overtime_rules: List['IOvertimeRule'],
    ) -> List[OvertimeInterval]:
        """Returns list of overtime intervals applicable to the given shift and employee."""
        pass

    # @abc.abstractmethod
    # def get_remaining_non_ot_hours(
    #         self,
    #         nurse_profile: NurseProfile,
    #         current_shift: Shift,
    #         nurse_shift_history: Dict[Shift, List[WorkedShiftSegment]],
    # ) -> float:
    #     pass

    # @abc.abstractmethod
    # def calculate_overtime_intervals(
    #         self,
    #         nurse_profile: NurseProfile,
    #         current_shift: Shift,
    #         nurse_shift_history: Dict[Shift, List[WorkedShiftSegment]],
    # ) -> List[pendulum.Interval]:
    #     pass


class IOvertimeRule(abc.ABC):
    """Abstraction for a single source of overtime requirement (State, Union, etc.)."""

    @property
    @abc.abstractmethod
    def multiplier(self) -> float:
        """The required multiplier for this rule (e.g., 1.5 or 2.0)."""
        pass

    # Optional: Add eligibility checks here if needed, though they are often factored
    # into the IOvertimeCalculator for simplicity.

    @property
    @abc.abstractmethod
    def priority(self) -> int:
        """Priority for tie-breaking: Higher number means checked first."""
        pass

    @property
    @abc.abstractmethod
    def applicable_job_titles(self) -> Optional[List[str]]:
        """List of job titles required for this rule."""
        pass

    @property
    # @abc.abstractmethod
    def required_certifications(self) -> Optional[List[str]]:
        """List of certifications required for this rule."""
        return None

    @property
    def certification_match_type(self) -> str:
        """Type of match for certifications: 'ALL' or 'ANY'."""
        return "ALL"

    @property
    @abc.abstractmethod
    def contract_id(self) -> Optional[str]:
        """The specific union/facility contract ID this rule belongs to."""
        pass


class IDifferentialRule(abc.ABC):
    @abc.abstractmethod
    def get_applicable_intervals_for_shift(
            self,
            shift: Shift,
    ) -> List[DifferentialDateInterval]:
        pass

    @property
    @abc.abstractmethod
    def differential(self) -> Differential:
        pass

    @property
    @abc.abstractmethod
    def priority(self) -> int:
        pass

    @property
    @abc.abstractmethod
    def applicable_job_titles(self) -> Optional[List[str]]:
        """List of job titles for which this rule applies. None means applies to all."""
        pass

    @property
    def required_certifications(self) -> Optional[List[str]]:
        """List of certifications required for this rule to apply."""
        return None

    @property
    def certification_match_type(self) -> str:
        """Type of match: 'ALL' (AND) or 'ANY' (OR). Defaults to 'ALL'."""
        return "ALL"


class IShiftSlicer(abc.ABC):
    """
    Slices a single shift into granular WorkedShiftSegments based on the
    start and end points of all overlapping differential and overtime intervals.
    """

    @abc.abstractmethod
    def slice_shift(
            self,
            shift: Shift,
            differential_intervals: List[DifferentialDateInterval],
            overtime_intervals: List[OvertimeInterval],
    ) -> List[WorkedShiftSegment]:
        pass


class IRateCalculator(abc.ABC):
    """Calculates the final effective rate for a single segment."""

    @abc.abstractmethod
    def calculate_effective_rate(
            self,
            compensation_record: StaffCompensationRecord,
            segment: WorkedShiftSegment,
    ) -> float:
        pass


class INurseDifferentialRetriever(abc.ABC):
    @abc.abstractmethod
    def get_differentials(self, nurse: NurseProfile, shift: Shift) -> List[Differential]:
        pass


class IStaffCompensationService(abc.ABC):
    """Defines the contract for retrieving the active financial rate for an employee."""

    @abc.abstractmethod
    def get_record_for_date(
            self,
            employee_id: str,
            check_date: pendulum.DateTime,
    ) -> Optional[StaffCompensationRecord]:
        """
        Retrieves the one StaffCompensationRecord whose validity period
        covers the check_date.
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


class IShiftReconcilerService(abc.ABC):
    """
    Defines the contract for combining scheduled shifts, raw punches, and
    business rules to determine the net time blocks worked.
    """

    @abc.abstractmethod
    def reconcile_shift_to_blocks(
            self,
            scheduled_shift: Shift,
            raw_punches: List[TimePunch],
    ) -> List[WorkedTimeBlock]:
        """
        Combines scheduled time and actual punches, applies rounding rules,
        and accounts for mandatory breaks to produce one or more contiguous
        WorkedTimeBlock objects.
        """
        pass


class IFacilityRulesService(abc.ABC):
    """
    Defines the contract for retrieving time-based payroll rules (rounding, deductions).
    """

    @abc.abstractmethod
    def apply_rounding(self, raw_time: pendulum.DateTime, punch_type: PunchType) -> pendulum.DateTime:
        """
        Applies facility-specific rounding rules (e.g., 6-minute rule, 15-minute rule)
        to a raw punch time.

        :param raw_time: The raw punch time (IN or OUT).
        :param punch_type: 'in' or 'out'.
        :return: The rounded pendulum.DateTime object.
        """
        pass

    @abc.abstractmethod
    def get_time_settings(
            self,
            employee_id: str,
            check_dt: pendulum.DateTime,
    ) -> EmployeeTimeSettings:
        """
        Retrieves complex time-related payroll settings (pairing threshold,
        split time, rounding unit) for a specific employee and date.
        """
        pass

    @abc.abstractmethod
    def get_meal_deduction_rules(self, check_dt: pendulum.DateTime) -> Optional[MealDeductionRules]:
        """
        Retrieves the mandatory meal deduction rules applicable on the given date/time,
        as these can change based on contract or state law.
        """
        pass


class IEmployeeRetriever(abc.ABC):
    """Defines the contract for retrieving core Employee identity records."""

    @abc.abstractmethod
    def get_employee_by_id(self, employee_id: str) -> Optional[Employee]:
        """Retrieves a single Employee record by their unique ID."""
        pass

    @abc.abstractmethod
    def get_all_employees(self) -> List[Employee]:
        """Retrieves all active Employee records."""
        pass


class IRuleRetrievalService(abc.ABC):
    """
    Defines the contract for efficiently retrieving all potentially applicable
    rules (Differential and Overtime) separately from the persistence layer.
    """

    @abc.abstractmethod
    def get_differential_rules_by_context(
            self,
            employee: 'Employee',
            shift: 'Shift',
    ) -> List['IDifferentialRule']:
        """
        Retrieves all active, non-time-specific differential rules (e.g., Weekend
        Differential) applicable to the employee and facility context.
        """
        pass

    @abc.abstractmethod
    def get_overtime_rules_by_context(
            self,
            employee: 'Employee',
            shift: 'Shift',
    ) -> List['IOvertimeRule']:
        """
        Retrieves all active overtime threshold rules (e.g., 8-hour daily OT,
        40-hour weekly OT, Union OT) applicable to the employee and date.
        """
        pass


class IShiftRequirementsRetriever(abc.ABC):
    @abc.abstractmethod
    def get_shift_requirements(self, shift: Shift) -> ShiftSpecificRequirements:
        pass
