import abc

import whenever

from snf_schedule_optimizer.models import (
    Differential,
    DifferentialDateInterval,
    Employee,
    EmployeeRuleOverride,
    EmployeeTimeSettings,
    FacilityRulesConfig,
    MealDeductionRules,
    NurseProfile,
    OvertimeInterval,
    PunchType,
    Shift,
    TimePunch,
    WorkedShiftSegment,
    WorkedTimeBlock,
)
from snf_schedule_optimizer.models.persistence_dtos import (
    DifferentialRuleData,
    OvertimeRuleData,
)

# region Payroll Service Interfaces


class IShiftSlicer(abc.ABC):
    """
    Slices a single shift into granular WorkedShiftSegments based on the
    start and end points of all overlapping differential and overtime intervals.
    """

    @abc.abstractmethod
    def slice_shift(
        self,
        shift: Shift,
        differential_intervals: list[DifferentialDateInterval],
        overtime_intervals: list[OvertimeInterval],
    ) -> list[WorkedShiftSegment]:
        pass


class IOvertimeCalculator(abc.ABC):
    """Determines which hours of a shift are subject to an OT multiplier."""

    @abc.abstractmethod
    async def get_overtime_intervals(
        self,
        shift: Shift,
        employee: Employee,
        work_shift_history: dict[Shift, list[WorkedShiftSegment]],
        overtime_rules: list["IOvertimeRule"],
    ) -> list[OvertimeInterval]:
        """Returns list of overtime intervals applicable to the given shift and employee."""
        pass


class IShiftReconcilerService(abc.ABC):
    """
    Defines the contract for combining scheduled shifts, raw punches, and
    business rules to determine the net time blocks worked.
    """

    @abc.abstractmethod
    async def reconcile_shift_to_blocks(
        self,
        scheduled_shift: Shift,
        raw_punches: list[TimePunch],
    ) -> list[WorkedTimeBlock]:
        """
        Combines scheduled time and actual punches, applies rounding rules,
        and accounts for mandatory breaks to produce one or more contiguous
        WorkedTimeBlock objects.
        """
        pass


# endregion

# region Overtime and Differential Rule Interfaces


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
    def applicable_job_titles(self) -> list[str] | None:
        """List of job titles required for this rule."""
        pass

    @property
    # @abc.abstractmethod
    def required_certifications(self) -> list[str] | None:
        """List of certifications required for this rule."""
        return None

    @property
    def certification_match_type(self) -> str:
        """Type of match for certifications: 'ALL' or 'ANY'."""
        return "ALL"

    @property
    @abc.abstractmethod
    def contract_id(self) -> str | None:
        """The specific union/facility contract ID this rule belongs to."""
        pass


class IDifferentialRule(abc.ABC):
    @abc.abstractmethod
    def get_applicable_intervals_for_shift(
        self,
        shift: Shift,
    ) -> list[DifferentialDateInterval]:
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
    def applicable_job_titles(self) -> list[str] | None:
        """List of job titles for which this rule applies. None means applies to all."""
        pass

    @property
    def required_certifications(self) -> list[str] | None:
        """List of certifications required for this rule to apply."""
        return None

    @property
    def certification_match_type(self) -> str:
        """Type of match: 'ALL' (AND) or 'ANY' (OR). Defaults to 'ALL'."""
        return "ALL"


class INurseDifferentialRepo(abc.ABC):
    @abc.abstractmethod
    def get_differentials(
        self,
        nurse: NurseProfile,
        shift: Shift,
    ) -> list[Differential]:
        pass


class IDifferentialRuleRepo(abc.ABC):
    @abc.abstractmethod
    async def get_all_rules(self, org_id: str) -> list[DifferentialRuleData]:
        pass


class IOvertimeRuleRepo(abc.ABC):
    @abc.abstractmethod
    async def get_all_rules(self, org_id: str) -> list[OvertimeRuleData]:
        pass


class IRuleRetrievalService(abc.ABC):
    """
    Defines the contract for efficiently retrieving all potentially applicable
    rules (Differential and Overtime) separately from the persistence layer.
    """

    @abc.abstractmethod
    async def get_differential_rules_by_context(
        self,
        employee: Employee,
        shift: Shift,
    ) -> list[IDifferentialRule]:
        """
        Retrieves all active, non-time-specific differential rules (e.g., Weekend
        Differential) applicable to the employee and facility context.
        """
        pass

    @abc.abstractmethod
    async def get_overtime_rules_by_context(
        self,
        employee: Employee,
        shift: Shift,
    ) -> list[IOvertimeRule]:
        """
        Retrieves all active overtime threshold rules (e.g., 8-hour daily OT,
        40-hour weekly OT, Union OT) applicable to the employee and date.
        """
        pass


class IFacilityRulesRepo(abc.ABC):
    """
    PORT: Interface for fetching raw rule configurations from persistence.
    """

    @abc.abstractmethod
    async def get_active_config(
        self,
        org_id: str,
        facility_id: str,
        check_date: whenever.ZonedDateTime,
    ) -> FacilityRulesConfig | None:
        pass


class IEmployeeRulesRepo:
    """
    Interface for fetching employee-specific rule overrides.
    """

    async def get_employee_rule_overrides(
        self,
        org_id: str,
        employee_id: str,
        check_date: whenever.ZonedDateTime,
    ) -> EmployeeRuleOverride | None:
        pass


class IFacilityRulesService(abc.ABC):
    """
    Defines the contract for retrieving time-based payroll rules (rounding, deductions).
    """

    @abc.abstractmethod
    async def apply_rounding(
        self,
        org_id: str,
        raw_time: whenever.ZonedDateTime,
        punch_type: PunchType,
    ) -> whenever.ZonedDateTime:
        """
        Applies facility-specific rounding rules (e.g., 6-minute rule, 15-minute rule)
        to a raw punch time.

        :param raw_time: The raw punch time (IN or OUT).
        :param punch_type: 'in' or 'out'.
        :return: The rounded whenever.Instant object.
        """
        pass

    @abc.abstractmethod
    async def get_time_settings(
        self,
        org_id: str,
        employee_id: str,
        facility_id: str,
        check_dt: whenever.ZonedDateTime,
    ) -> EmployeeTimeSettings:
        """
        Retrieves complex time-related payroll settings (pairing threshold,
        split time, rounding unit) for a specific employee and date.
        """
        pass

    @abc.abstractmethod
    async def get_meal_deduction_rules(
        self,
        org_id: str,
        facility_id: str,
        check_dt: whenever.ZonedDateTime,
    ) -> MealDeductionRules | None:
        """
        Retrieves the mandatory meal deduction rules applicable on the given date/time,
        as these can change based on contract or state law.
        """
        pass


# endregion
