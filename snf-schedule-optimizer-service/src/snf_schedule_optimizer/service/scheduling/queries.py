"""Query services for schedule read operations."""

from typing import NamedTuple

from snf_schedule_optimizer.domain.exceptions import (
    EntityNotFoundError,
    InvalidRequestError,
)
from snf_schedule_optimizer.domain.repositories import IFacilityRepo, IShiftRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IOptimizationRunRepo,
    IScheduleRepo,
    ScheduleLookupKey,
)
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    FacilityConfig,
    OptimizationRun,
    Schedule,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.persistence.read_repo.schedule_read_repo import (
    ScheduleReadRepo,
)


class ScheduleStatusResult(NamedTuple):
    schedule: Schedule | None
    active_run: OptimizationRun | None
    has_newer_version: bool


class MonthlyScheduleResult(NamedTuple):
    schedule: Schedule | None
    shifts: dict[ShiftKey, Shift]
    employees: dict[int, Employee]
    facility_config: FacilityConfig | None


class ScheduleQueryService:
    """Read-only query service for schedule data."""

    def __init__(
        self,
        schedule_retriever: IScheduleRepo,
        optimization_run_repo: IOptimizationRunRepo,
        facility_repository: IFacilityRepo,
        shift_retriever: IShiftRepo,
        provider_factory: ScenarioDataProviderFactory,
        schedule_read_repo: ScheduleReadRepo | None = None,
    ):
        self._schedule_retriever = schedule_retriever
        self._optimization_run_repo = optimization_run_repo
        self._facility_repository = facility_repository
        self._shift_retriever = shift_retriever
        self._provider_factory = provider_factory
        self._schedule_read_repo = schedule_read_repo

    async def get_optimization_run(self, run_id: str) -> OptimizationRun | None:
        return await self._optimization_run_repo.get_optimization_run(run_id)

    async def get_optimization_run_by_client_request(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        schedule_id: DomainPrimaryKeyType,
        client_request_id: str,
    ) -> OptimizationRun | None:
        return await self._optimization_run_repo.get_optimization_run_by_client_request(
            org_id, facility_id, schedule_id, client_request_id
        )

    async def get_schedule_status(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        schedule_id: DomainPrimaryKeyType,
        current_schedule_version: int,
    ) -> ScheduleStatusResult:
        schedule = await self._schedule_retriever.get_schedule(
            ScheduleLookupKey(org_id, schedule_id)
        )
        if schedule is None:
            return ScheduleStatusResult(
                schedule=None, active_run=None, has_newer_version=False
            )
        active_run = await self._optimization_run_repo.get_active_optimization_run(
            org_id, facility_id, schedule_id
        )
        latest_version = await self._schedule_retriever.get_latest_schedule_version(
            org_id, schedule_id
        )
        has_newer_version = (
            latest_version or schedule.schedule_version
        ) > current_schedule_version
        return ScheduleStatusResult(
            schedule=schedule,
            active_run=active_run,
            has_newer_version=has_newer_version,
        )

    async def get_monthly_schedule(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType | None,
        start_date: str,
    ) -> MonthlyScheduleResult:
        schedule = await self._schedule_retriever.get_schedule_for_month(
            org_id=org_id, facility_id=facility_id, start_date=start_date
        )
        if schedule is None:
            return MonthlyScheduleResult(
                schedule=None, shifts={}, employees={}, facility_config=None
            )
        target_facility_id = (
            facility_id if facility_id is not None else schedule.facility_id
        )
        if target_facility_id is None:
            raise InvalidRequestError(
                "A facility_id is required to load a monthly schedule."
            )
        configs = await self._facility_repository.get_configs(
            org_id, [target_facility_id]
        )
        if not configs:
            raise EntityNotFoundError(
                f"Facility config not found for facility_id: {target_facility_id}"
            )
        facility_config = configs[0]
        timezone_map = {facility_config.facility_id: facility_config.tz}
        shift_keys = [
            key
            for key in schedule.shift_assignments
            if key.facility_id == target_facility_id
        ]
        shifts = await self._shift_retriever.get_shifts_by_keys(
            shift_keys=shift_keys, facility_timezones=timezone_map, org_id=org_id
        )
        employees = await self._provider_factory.employee_retriever.get_all_employees(
            org_id
        )
        employee_map = {employee.employee_id: employee for employee in employees}
        return MonthlyScheduleResult(
            schedule=schedule,
            shifts=shifts,
            employees=employee_map,
            facility_config=facility_config,
        )
