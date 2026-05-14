import logging
import time

import whenever

from snf_schedule_optimizer.domain.hr.interfaces import (
    IEmployeeRepo,
    IStaffCompensationRepo,
)
from snf_schedule_optimizer.domain.timekeeping.interfaces import (
    IEmployeeWorkHistoryService,
)
from snf_schedule_optimizer.ml_output_repo import IMLModelOutputsRepo
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    FacilityConfig,
    FacilityIdType,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    HprdShiftNurseRequirementHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import (
    IHprdRequirementCalculator,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.persistence import INurseRepo
from snf_schedule_optimizer.scenario import CandidateEligibilityService

logger = logging.getLogger(__name__)


class ScenarioDataProviderImpl(IScenarioDataProvider):
    """
    Concrete implementation that uses injected raw retrievers to fetch data
    on demand and caches results for the lifetime of this object instance.
    """

    def __init__(
        self,
        target_org_id: DomainPrimaryKeyType,
        facility_contexts: dict[FacilityIdType, FacilityScenarioContext],
        # shifts: List["Shift"],  # The scope of this scenario
        # config: "FacilityConfig",
        employee_retriever: IEmployeeRepo,
        nurse_retriever: INurseRepo,
        hprd_calculator: IHprdRequirementCalculator,
        staff_comp_service: IStaffCompensationRepo,
        ml_model_retriever: IMLModelOutputsRepo,
        work_history_service: IEmployeeWorkHistoryService,
        pay_period_start: whenever.Instant,
        optimization_start_time: whenever.Instant,
        optimization_settings: OptimizationSettings,
        # min_mandates: "MinMandates",
    ):
        self.target_org_id = target_org_id

        # --- TENANT SECURITY CHECK ---
        for fac_id, context in facility_contexts.items():
            # 1. Check Facility Config
            if context.config.org_id != target_org_id:
                # raise SecurityError(f"Security Alert: Attempted to load facility {fac_id} from wrong org!")
                raise Exception(
                    f"Security Alert: Attempted to load facility {fac_id} from wrong org!"
                )

            # 2. Check Shifts
            for shift in context.shifts:
                if shift.org_id != target_org_id:
                    # raise SecurityError(
                    raise Exception(
                        f"Data Integrity Error: Shift {shift.shift_id} belongs to "
                        f"org {shift.org_id}, but run is for {target_org_id}"
                    )

        # --- SANITY CHECK ---
        for fac_id, context in facility_contexts.items():
            for shift in context.shifts:
                if shift.facility_id != fac_id:
                    raise ValueError(
                        f"Data Integrity Error: Shift {shift.shift_id} belongs to "
                        f"{shift.facility_id} but was found in context for {fac_id}"
                    )

        self._facility_contexts = facility_contexts
        # self._shifts = shifts
        # self._config = config
        self._employee_retriever = employee_retriever
        self._nurse_retriever = nurse_retriever
        self._hprd_calculator = hprd_calculator
        self._staff_comp_service = staff_comp_service
        self._ml_model_retriever = ml_model_retriever
        self._work_history_service = work_history_service
        self._optimization_settings = optimization_settings

        self.pay_period_start = pay_period_start
        self.opt_start = optimization_start_time
        # self._min_mandates = min_mandates

        # Internal Caches for parameterized data
        self._shift_nurses_cache: dict[ShiftKey, list[NurseProfile]] = {}
        self._cached_all_employees: list[Employee] | None = None
        self._cached_employees_by_id: dict[DomainPrimaryKeyType, Employee] | None = None
        self._cached_hprd_reqs: dict[int, HprdShiftNurseRequirementHolder] = {}
        self._accumulated_hours_cache: dict[DomainPrimaryKeyType, float] = {}
        self._cached_comp_records: dict[DomainPrimaryKeyType, StaffCompensationRecord] | None = None
        self._work_history_preloaded = False
        self._candidate_eligibility_service = CandidateEligibilityService()

    def get_org_id(self) -> DomainPrimaryKeyType:
        """Returns the organization ID for this optimization run."""
        return self.target_org_id

    # FIX 13: Removed @cached_property, used manual caching to match interface signature
    async def get_all_employees(self) -> list[Employee]:
        if self._cached_all_employees is None:
            t0 = time.perf_counter()
            self._cached_all_employees = (
                await self._employee_retriever.get_all_employees(
                    org_id=self.target_org_id
                )
            )
            logger.info(
                "Loaded %d employees in %.2fs",
                len(self._cached_all_employees),
                time.perf_counter() - t0,
            )
        return self._cached_all_employees

    async def get_employee_by_id(
        self, employee_id: DomainPrimaryKeyType
    ) -> Employee | None:
        if self._cached_employees_by_id is None:
            self._cached_employees_by_id = {
                employee.employee_id: employee
                for employee in await self.get_all_employees()
            }
        return self._cached_employees_by_id.get(employee_id)

    # FIX 14: Removed @cached_property, used manual caching
    async def get_hprd_requirements_for_facility(
        self,
        facility_id: DomainPrimaryKeyType,
    ) -> HprdShiftNurseRequirementHolder:
        if facility_id not in self._cached_hprd_reqs:
            # print(f"Calculating heavy HPRD math for fac {facility_id}...")
            context = self._facility_contexts[facility_id]
            self._cached_hprd_reqs[
                facility_id
            ] = await self._hprd_calculator.calculate_requirements(context)
        return self._cached_hprd_reqs[facility_id]

    # --- Case 2: Parameterized data cached manually with dicts ---
    async def get_nurses_for_shift(self, shift: Shift) -> list[NurseProfile]:
        if shift.shift_key not in self._shift_nurses_cache:
            nurses = await self._nurse_retriever.get_nurses(shift)
            eligible_nurses = []
            for nurse in nurses:
                employee = await self.get_employee_by_id(nurse.employee_id)
                worked_hours = await self.get_accumulated_hours_for_pay_period(
                    nurse.employee_id
                )
                result = self._candidate_eligibility_service.evaluate(
                    nurse=nurse,
                    employee=employee,
                    shift=shift,
                    already_worked_hours=worked_hours,
                )
                if result.eligible:
                    eligible_nurses.append(nurse)
            self._shift_nurses_cache[shift.shift_key] = eligible_nurses

        return self._shift_nurses_cache[shift.shift_key]

    def get_compensation_service(self) -> IStaffCompensationRepo:
        return self._staff_comp_service

    def get_ml_model_outputs(self, shift: Shift) -> MlModelOutputs:
        return self._ml_model_retriever.get_model_outputs(shift)

    async def get_accumulated_hours_for_pay_period(
        self, employee_id: DomainPrimaryKeyType
    ) -> float:
        if employee_id in self._accumulated_hours_cache:
            return self._accumulated_hours_cache[employee_id]

        if not self._work_history_preloaded:
            await self._warmup_work_history()

        return self._accumulated_hours_cache.get(employee_id, 0.0)

    async def _warmup_work_history(self) -> None:
        if self._work_history_preloaded:
            return
        t0 = time.perf_counter()
        employees = await self.get_all_employees()
        employee_ids = [e.employee_id for e in employees]
        if not employee_ids:
            self._work_history_preloaded = True
            return
        hours_map = await self._work_history_service.preload_all_accumulated_hours(
            org_id=self.target_org_id,
            employee_ids=employee_ids,
            check_date=self.opt_start,
            pay_period_start=self.pay_period_start,
            facility_id=None,
        )
        self._accumulated_hours_cache.update(hours_map)
        self._work_history_preloaded = True
        logger.info(
            "Work history preloaded for %d employees in %.2fs",
            len(hours_map),
            time.perf_counter() - t0,
        )

    async def _warmup_compensation(self) -> None:
        if self._cached_comp_records is not None:
            return
        t0 = time.perf_counter()
        self._cached_comp_records = (
            await self._staff_comp_service.get_all_records_for_org(
                org_id=self.target_org_id,
                check_date=self.opt_start.to_tz("UTC").date(),
            )
        )
        logger.info(
            "Compensation preloaded for %d employees in %.2fs",
            len(self._cached_comp_records),
            time.perf_counter() - t0,
        )

    async def get_compensation_for_date(
        self,
        employee_id: DomainPrimaryKeyType,
        check_date: whenever.Date,
    ) -> StaffCompensationRecord | None:
        if self._cached_comp_records is None:
            await self._warmup_compensation()
        assert self._cached_comp_records is not None
        return self._cached_comp_records.get(employee_id)

    def get_facility_ids(self) -> list[FacilityIdType]:
        return list(self._facility_contexts.keys())

    def get_shifts_for_facility(self, facility_id: DomainPrimaryKeyType) -> list[Shift]:
        return self._facility_contexts[facility_id].shifts

    def get_all_shifts(self) -> list[Shift]:
        all_shifts = []
        for context in self._facility_contexts.values():
            all_shifts.extend(context.shifts)
        return all_shifts

    def get_facility_config(self, facility_id: DomainPrimaryKeyType) -> FacilityConfig:
        return self._facility_contexts[facility_id].config

    def get_optimization_settings(self) -> OptimizationSettings:
        return self._optimization_settings


class ScenarioDataProviderFactory:
    """
    Holds the raw, long-lived retriever instances and knows how to
    create a scoped ScenarioDataProviderImpl for a specific run.
    """

    def __init__(
        self,
        employee_retriever: IEmployeeRepo,
        nurse_retriever: INurseRepo,
        hprd_calculator: IHprdRequirementCalculator,
        staff_compensation_service: IStaffCompensationRepo,
        ml_model_retriever: IMLModelOutputsRepo,
        work_history_service: IEmployeeWorkHistoryService,
    ):
        self.employee_retriever = employee_retriever
        self.nurse_retriever = nurse_retriever
        self.hprd_calculator = hprd_calculator
        self.staff_compensation_service = staff_compensation_service
        self.ml_model_retriever = ml_model_retriever
        self.work_history_service = work_history_service

    def create(
        self,
        org_id: DomainPrimaryKeyType,
        facility_contexts: dict[DomainPrimaryKeyType, FacilityScenarioContext],
        pay_period_start: whenever.Instant,
        optimization_start_time: whenever.Instant,
        optimization_settings: OptimizationSettings,
    ) -> IScenarioDataProvider:
        return ScenarioDataProviderImpl(
            target_org_id=org_id,
            facility_contexts=facility_contexts,
            employee_retriever=self.employee_retriever,
            nurse_retriever=self.nurse_retriever,
            hprd_calculator=self.hprd_calculator,
            staff_comp_service=self.staff_compensation_service,
            ml_model_retriever=self.ml_model_retriever,
            work_history_service=self.work_history_service,
            pay_period_start=pay_period_start,
            optimization_start_time=optimization_start_time,
            optimization_settings=optimization_settings,
        )
