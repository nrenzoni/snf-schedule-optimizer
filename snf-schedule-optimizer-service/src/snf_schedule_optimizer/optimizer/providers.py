import whenever

from snf_schedule_optimizer.ml_output_retrievers import IMLModelOutputsRetriever
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    MlModelOutputs,
    NurseProfile,
    Shift,
)
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    HprdShiftNurseRequirementHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import (
    IHprdRequirementCalculator,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.persistence import INurseRetriever
from snf_schedule_optimizer.services.hr.interfaces import (
    IEmployeeRetriever,
    IStaffCompensationService,
)
from snf_schedule_optimizer.services.timekeeping.interfaces import (
    IEmployeeWorkHistoryService,
)


class ScenarioDataProviderImpl(IScenarioDataProvider):
    """
    Concrete implementation that uses injected raw retrievers to fetch data
    on demand and caches results for the lifetime of this object instance.
    """

    def __init__(
        self,
        target_org_id: str,
        facility_contexts: dict[str, FacilityScenarioContext],
        # shifts: List["Shift"],  # The scope of this scenario
        # config: "FacilityConfig",
        employee_retriever: IEmployeeRetriever,
        nurse_retriever: INurseRetriever,
        hprd_calculator: IHprdRequirementCalculator,
        staff_comp_service: IStaffCompensationService,
        ml_model_retriever: IMLModelOutputsRetriever,
        work_history_service: IEmployeeWorkHistoryService,
        pay_period_start: whenever.Instant,
        optimization_start_time: whenever.Instant,
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

        self.pay_period_start = pay_period_start
        self.opt_start = optimization_start_time
        # self._min_mandates = min_mandates

        # Internal Caches for parameterized data
        self._shift_nurses_cache: dict[str, list[NurseProfile]] = {}
        self._cached_all_employees: list[Employee] | None = None
        self._cached_hprd_reqs: dict[str, HprdShiftNurseRequirementHolder] = {}
        self._accumulated_hours_cache: dict[str, float] = {}

    def get_org_id(self) -> str:
        """Returns the organization ID for this optimization run."""
        return self.target_org_id

    # FIX 13: Removed @cached_property, used manual caching to match interface signature
    def get_all_employees(self) -> list[Employee]:
        if self._cached_all_employees is None:
            print("Fetching all employees from source...")
            self._cached_all_employees = self._employee_retriever.get_all_employees()
        return self._cached_all_employees

    def get_employee_by_id(self, employee_id: str) -> Employee | None:
        # Simple lookup from pre-fetched list
        for emp in self.get_all_employees():
            if emp.employee_id == employee_id:
                return emp
        return None

    # FIX 14: Removed @cached_property, used manual caching
    def get_hprd_requirements_for_facility(
        self,
        facility_id: str,
    ) -> HprdShiftNurseRequirementHolder:
        if facility_id not in self._cached_hprd_reqs:
            # print(f"Calculating heavy HPRD math for fac {facility_id}...")
            context = self._facility_contexts[facility_id]
            self._cached_hprd_reqs[facility_id] = (
                self._hprd_calculator.calculate_requirements(context)
            )
        return self._cached_hprd_reqs[facility_id]

    # --- Case 2: Parameterized data cached manually with dicts ---
    def get_nurses_for_shift(self, shift: Shift) -> list[NurseProfile]:
        # Use shift_id as the cache key
        if shift.shift_id not in self._shift_nurses_cache:
            # print(f"Fetching nurses for shift {shift.shift_id}...")
            # Call the raw retriever
            nurses = self._nurse_retriever.get_nurses(shift)
            self._shift_nurses_cache[shift.shift_id] = nurses

        return self._shift_nurses_cache[shift.shift_id]

    def get_compensation_service(self) -> IStaffCompensationService:
        return self._staff_comp_service

    def get_ml_model_outputs(self, shift: Shift) -> MlModelOutputs:
        return self._ml_model_retriever.get_model_outputs(shift)

    def get_accumulated_hours_for_pay_period(self, employee_id: str) -> float:
        if employee_id in self._accumulated_hours_cache:
            return self._accumulated_hours_cache[employee_id]

        # 1. Fetch the raw history segments from your existing service
        history = self._work_history_service.get_processed_history_for_period(
            org_id=self.target_org_id,
            employee_id=employee_id,
            check_date=self.opt_start,
            facility_id=None,
        )

        # 2. Calculate the total hours (You can use the service's calculator or sum it manually here)
        # Assuming get_accumulated_hours needs specific contexts,
        # or we can do a simple sum if your segments have a 'duration' property:
        total_hours = 0.0
        for segments in history.values():
            for segment in segments:
                # Ensure the segment is within the current pay week window
                if segment.start_time >= self.pay_period_start:
                    total_hours += segment.duration_hours

        self._accumulated_hours_cache[employee_id] = total_hours
        return total_hours

    def get_facility_ids(self) -> list[str]:
        return list(self._facility_contexts.keys())

    def get_shifts_for_facility(self, facility_id: str) -> list[Shift]:
        return self._facility_contexts[facility_id].shifts

    def get_all_shifts(self) -> list[Shift]:
        all_shifts = []
        for context in self._facility_contexts.values():
            all_shifts.extend(context.shifts)
        return all_shifts

    def get_facility_config(self, facility_id: str) -> FacilityConfig:
        return self._facility_contexts[facility_id].config


class ScenarioDataProviderFactory:
    """
    Holds the raw, long-lived retriever instances and knows how to
    create a scoped ScenarioDataProviderImpl for a specific run.
    """

    def __init__(
        self,
        employee_retriever: IEmployeeRetriever,
        nurse_retriever: INurseRetriever,
        hprd_calculator: IHprdRequirementCalculator,
        staff_compensation_service: IStaffCompensationService,
        ml_model_retriever: IMLModelOutputsRetriever,
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
        org_id: str,
        facility_contexts: dict[str, FacilityScenarioContext],
        pay_period_start: whenever.Instant,
        optimization_start_time: whenever.Instant,
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
        )
