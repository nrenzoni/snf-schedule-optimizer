import whenever

from snf_schedule_optimizer.domain.hr.interfaces import (
    IEmployeeRepo,
    IStaffCompensationRepo,
)
from snf_schedule_optimizer.domain.payroll.calculations.overtime_calculation import (
    ThresholdOvertimeRule,
)
from snf_schedule_optimizer.domain.payroll.interfaces import IFacilityRulesService
from snf_schedule_optimizer.domain.repositories import (
    IFacilityRepo,
    IShiftRepo,
)
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IPreferencePenaltyProcessor,
    IScheduleRepo,
    IShiftRequirementsRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.domain.timekeeping.interfaces import (
    IEmployeeWorkHistoryService,
)
from snf_schedule_optimizer.ml_output_repo import IMLModelOutputsRepo

# Import Models
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    EmployeeTimeSettings,
    FacilityConfig,
    FacilityIdType,
    HprdEnforcedRole,
    LookbackPeriod,
    MealDeductionRules,
    MlModelOutputs,
    NurseProfile,
    PreferenceWeights,
    PunchType,
    RoundingType,
    Schedule,
    Shift,
    ShiftKey,
    ShiftSpecificRequirements,
    SplitDayType,
    StaffCompensationRecord,
    WorkedShiftSegment,
)
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    HprdShiftNurseRequirementHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import IHprdRequirementCalculator

# Import your Interfaces
from snf_schedule_optimizer.persistence.nurse_repo import INurseRepo
from snf_schedule_optimizer.utils.time_utils import TimeRoundingUtility


class FakeEmployeeRepo(IEmployeeRepo):
    def __init__(self, employees: list[Employee]):
        self._employees = employees

    async def get_all_employees(
        self,
        org_id: DomainPrimaryKeyType,
    ) -> list[Employee]:
        return self._employees

    async def get_employee_by_id(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
    ) -> Employee | None:
        return next((e for e in self._employees if e.employee_id == employee_id), None)

    async def save_employee(
        self, org_id: DomainPrimaryKeyType, employee: Employee
    ) -> None:
        # For the fake, we won't actually persist anything.
        pass


class FakeNurseRepo(INurseRepo):
    def __init__(self, nurses: list[NurseProfile]):
        self._nurses = nurses

    async def get_nurses(self, shift: Shift) -> list[NurseProfile]:
        # Simple Fake: Returns all configured nurses regardless of shift
        # You could add filtering logic here if you wanted smarter tests
        return self._nurses

    async def get_nurse(self, employee_id: DomainPrimaryKeyType) -> NurseProfile | None:
        return next((n for n in self._nurses if n.employee_id == employee_id), None)

    async def save_nurse_profile(
        self, org_id: DomainPrimaryKeyType, nurse: NurseProfile
    ) -> None:
        pass


class FakeStaffCompensationRepo(IStaffCompensationRepo):
    def __init__(self, records: list[StaffCompensationRecord]):
        self._records = records
        self.tz = "America/New_York"

        self.employee_records: dict[
            DomainPrimaryKeyType, list[StaffCompensationRecord]
        ] = {}

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

    async def get_record_for_date(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        check_date: whenever.Date,
    ) -> StaffCompensationRecord | None:
        """
        Retrieves the one StaffCompensationRecord whose validity period
        covers the check_date.
        """

        if employee_id not in self.employee_records:
            return None

        # Check date should be compared to simple date for consistency with database storage

        for record in self.employee_records[employee_id]:
            # Check 1: Must be effective on or before the check date
            is_start_valid = record.effective_start_date <= check_date

            # Check 2: Must not be expired before the check date
            is_end_valid = (
                record.effective_end_date is None
                or record.effective_end_date > check_date
            )

            if is_start_valid and is_end_valid:
                return record

        return None

    async def save_compensation_record(
        self, org_id: DomainPrimaryKeyType, record: StaffCompensationRecord
    ) -> None:
        pass


class FakeWorkHistoryService(IEmployeeWorkHistoryService):
    def __init__(self, accumulated_hours_map: dict[DomainPrimaryKeyType, float]):
        self._hours_map = accumulated_hours_map

    async def get_processed_history_for_period(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        check_date: whenever.Instant,
        facility_id: DomainPrimaryKeyType | None = None,
    ) -> dict[ShiftKey, list[WorkedShiftSegment]]:
        # We don't need to return complex segments if we override the provider logic,
        # but to satisfy the type checker:
        return {}

    async def get_remaining_non_ot_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        ot_rules: list[ThresholdOvertimeRule],
    ) -> dict[LookbackPeriod, float]:
        raise NotImplementedError()

    async def get_accumulated_hours(
        self,
        employee: Employee,
        current_shift: Shift,
        history: dict[ShiftKey, list[WorkedShiftSegment]],
        threshold_hours: float,
        lookback_period: LookbackPeriod,
        work_period_start_day: whenever.Weekday | None = None,
        work_period_start_time: whenever.Time | None = None,
    ) -> float:
        return self._hours_map.get(employee.employee_id, 0.0)

    def get_consecutive_days_worked(
        self,
        employee: Employee,
        current_shift: Shift,
        history: dict[Shift, list[WorkedShiftSegment]],
        max_consecutive_days: int,
    ) -> list[whenever.Date]:
        return []


class FakeMLModelRepo(IMLModelOutputsRepo):
    def __init__(self, default_model_outputs: MlModelOutputs):
        self.default_model_outputs = default_model_outputs

    def get_model_outputs(self, shift: Shift) -> MlModelOutputs:
        return self.default_model_outputs


class FakePreferencePenaltyProcessor(IPreferencePenaltyProcessor):
    def __init__(self, penalty_map: dict[str, float] | None = None):
        """
        Args:
            penalty_map: A dictionary mapping "employee_id:shift_id" -> float penalty cost.
        """
        self._penalty_map = penalty_map or {}

    async def calculate_penalty_cost(
        self,
        employee: Employee,
        nurse: NurseProfile,
        shift: Shift,
        weights: PreferenceWeights,
    ) -> float:
        # Construct a simple composite key to lookup the pre-configured penalty
        key = f"{employee.employee_id}:{shift.shift_id}"

        # Return the configured float, or 0.0 to safely allow addition
        return self._penalty_map.get(key, 0.0)


class ShiftRequirementsRepoImpl(IShiftRequirementsRepo):
    """same requirements for all shifts implementation"""

    def __init__(self, default_requirements: ShiftSpecificRequirements):
        self.default_requirements = default_requirements

    async def get_shift_requirements(
        self, shift: Shift
    ) -> ShiftSpecificRequirements | None:
        return self.default_requirements


class FakeShiftRequirementsRepo(IShiftRequirementsRepo):
    def __init__(
        self,
        requirements_map: dict[DomainPrimaryKeyType, ShiftSpecificRequirements]
        | None = None,
        default_requirements: ShiftSpecificRequirements | None = None,
    ):
        """
        Args:
            requirements_map: Map of shift_id -> specific requirements.
            default_requirements: Returned if shift_id is not in the map.
        """
        self._map = requirements_map or {}
        # Create a zeroed-out default if none provided (mimics your previous MagicMock 0.0 behavior)
        self._default = default_requirements or ShiftSpecificRequirements(
            target_hprd_rn=0.0, target_hprd_cna=0.0, target_total_hprd=0.0
        )

    async def get_shift_requirements(
        self, shift: Shift
    ) -> ShiftSpecificRequirements | None:
        return self._map.get(shift.shift_id, self._default)


class FakeHprdRequirementCalculator(IHprdRequirementCalculator):
    def __init__(
        self,
        requirements_map: dict[tuple[DomainPrimaryKeyType, HprdEnforcedRole], float]
        | None = None,
    ):
        """
        Args:
            requirements_map: Dictionary mapping (shift_id, Role) -> required_count (float)
        """
        self._map = requirements_map or {}

    async def calculate_requirements(
        self, context: FacilityScenarioContext
    ) -> HprdShiftNurseRequirementHolder:
        # 1. Create the REAL holder data structure
        holder = HprdShiftNurseRequirementHolder(
            [s.shift_id for s in context.shifts],
            [HprdEnforcedRole.RN, HprdEnforcedRole.CNA],
        )

        # 2. Populate it with our test data
        for (shift_id, role), count in self._map.items():
            # Only set if the shift is actually part of this optimization run
            if shift_id in holder.shifts:
                holder[shift_id, role] = count

        return holder


class FakeFacilityRulesService(IFacilityRulesService):
    """
    Concrete implementation providing static, hardcoded payroll rules for testing
    the Shift Reconciler and other domain.
    """

    def __init__(self) -> None:
        # Hardcode the essential parameters for internal use
        self.DEFAULT_ROUNDING_UNIT = 6
        self.DEFAULT_PAIRING_THRESHOLD = whenever.DateTimeDelta(hours=10)
        self.DEFAULT_SPLIT_TIME = whenever.Time(3, 0, 0)
        self.DEFAULT_GRACE_WINDOW = whenever.DateTimeDelta(minutes=15)

        # Instantiate the deduction rules once
        self.default_meal_rules = MealDeductionRules(
            meal_threshold_hours=6.0,
            meal_duration_hours=0.5,  # 30 minutes
            is_mandatory=True,
        )

    async def apply_rounding(
        self,
        raw_time: whenever.ZonedDateTime,
        punch_type: PunchType,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
    ) -> whenever.ZonedDateTime:
        """
        Applies a standard nearest-interval rounding (e.g., 6-minute rule).
        """
        return TimeRoundingUtility.round_to_nearest_unit(
            raw_time,
            self.DEFAULT_ROUNDING_UNIT,
        )

    async def get_time_settings(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        check_dt: whenever.ZonedDateTime,
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

    async def get_meal_deduction_rules(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        check_dt: whenever.ZonedDateTime,
    ) -> MealDeductionRules | None:
        """
        Retrieves the standard 6-hour threshold/30-minute mandatory deduction rules.
        """
        # In production, this would check state/federal laws and return the applicable rule.
        return self.default_meal_rules


class FakeScheduleRepo(IScheduleRepo):
    """InMemory implementation of IScheduleRetriever for testing."""

    def __init__(self, schedules: dict[ScheduleLookupKey, Schedule] | None = None):
        # Key: (schedule_id, org_id) -> Schedule
        self._schedules = schedules or {}

    async def get_schedule(
        self,
        schedule_lookup: ScheduleLookupKey,
    ) -> Schedule | None:
        return self._schedules.get(schedule_lookup)

    async def get_schedule_for_month(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType | None,
        start_date: str,
    ) -> Schedule | None:
        for key, schedule in self._schedules.items():
            if key.org_id != org_id:
                continue
            if facility_id is not None and schedule.facility_id != facility_id:
                continue
            return schedule
        return None

    async def save_schedule(self, schedule: Schedule) -> None:
        if schedule.schedule_id is None:
            raise ValueError("schedule_id is required")
        self._schedules[ScheduleLookupKey(schedule.org_id, schedule.schedule_id)] = schedule


class FakeFacilityRepo(IFacilityRepo):
    """InMemory implementation of IFacilityRepository for testing."""

    def __init__(self, configs: list[FacilityConfig] | None = None):
        self._configs = {c.facility_id: c for c in (configs or [])}

    async def get_configs(
        self,
        org_id: DomainPrimaryKeyType,
        facility_ids: list[DomainPrimaryKeyType] | None = None,
    ) -> list[FacilityConfig]:
        if facility_ids is None:
            return [c for c in self._configs.values() if c.org_id == org_id]
        return [
            self._configs[fid]
            for fid in facility_ids
            if fid in self._configs and self._configs[fid].org_id == org_id
        ]

    async def get_all_facilities(self) -> list[FacilityConfig]:
        raise NotImplementedError()

    async def save_config(self, config: FacilityConfig) -> None:
        pass


class FakeShiftRepo(IShiftRepo):
    """InMemory implementation of IShiftRetriever for testing."""

    def __init__(self, shifts: list[Shift] | None = None):
        self._shifts = shifts or []

    async def get_shifts_for_org(
        self,
        org_id: DomainPrimaryKeyType,
        facility_timezones: dict[DomainPrimaryKeyType, str],
    ) -> list[Shift]:
        # Simple filtering. In real implementation, this might hydrate timezones.
        return [s for s in self._shifts if s.org_id == org_id]

    async def get_shifts_by_keys(
        self,
        shift_keys: list[ShiftKey],
        facility_timezones: dict[FacilityIdType, str],
        org_id: DomainPrimaryKeyType,
    ) -> dict[ShiftKey, Shift]:
        # Filter shifts matching the keys
        # We assume Shift objects in self._shifts already have the correct properties
        key_set = set(shift_keys)
        result = {}
        for s in self._shifts:
            # Construct key from shift
            s_key = ShiftKey(s.facility_id, s.shift_id)
            if s_key in key_set and s.org_id == org_id:
                result[s_key] = s
        return result

    async def save_shift(self, org_id: DomainPrimaryKeyType, shift: Shift) -> None:
        pass
