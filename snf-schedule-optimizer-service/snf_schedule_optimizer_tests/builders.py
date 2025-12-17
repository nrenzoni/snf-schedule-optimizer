from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    MlModelOutputs,
    NurseProfile,
    ResidentAcuity,
    Schedule,
    Shift,
    ShiftKey,
    ShiftSpecificRequirements,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.calculators import (
    HprdRequirementCalculatorImpl,
    NurseHardBlockCheckerImpl,
)
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    IHprdRequirementCalculator,
    IObjectivePenaltyStrategy,
    IPayModelStrategy,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    HprdStaffingConstraintStrategy,
)
from snf_schedule_optimizer.optimizer.strategies.pay import WeeklyVolumePayStrategy
from snf_schedule_optimizer.optimizer.strategies.penalties import QualityOfLifeStrategy
from snf_schedule_optimizer.optimizer.strategies.variables import (
    CoreVariableGenerationStrategy,
)
from snf_schedule_optimizer.resident_acuity_retrievers import (
    ResidentAcuityPerShiftRetrieverImpl,
)
from snf_schedule_optimizer.schedule_cost_evaluator import ScheduleCostEvaluator
from snf_schedule_optimizer.services.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.services.payroll.calculations.shift_slicers import (
    TimeOverlapShiftSlicer,
)
from snf_schedule_optimizer.services.repositories import (
    IFacilityRepository,
    IShiftRetriever,
)
from snf_schedule_optimizer.services.scheduling.interfaces import IScheduleRetriever
from snf_schedule_optimizer.services.scheduling.scheduler_facade import (
    WorkforceSchedulerService,
)

from .fakes import (
    FakeEmployeeRetriever,
    FakeMLModelRetriever,
    FakeNurseRetriever,
    FakePreferencePenaltyProcessor,
    FakeShiftRequirementsRetriever,
    FakeStaffCompensationService,
    FakeWorkHistoryService,
)


class FakeScheduleRetriever(IScheduleRetriever):
    """InMemory implementation of IScheduleRetriever for testing."""

    def __init__(self, schedules: dict[tuple[str, str], Schedule] | None = None):
        # Key: (schedule_id, org_id) -> Schedule
        self._schedules = schedules or {}

    def get_schedule(self, schedule_id: str, org_id: str) -> Schedule | None:
        return self._schedules.get((schedule_id, org_id))


class FakeFacilityRepository(IFacilityRepository):
    """InMemory implementation of IFacilityRepository for testing."""

    def __init__(self, configs: list[FacilityConfig] | None = None):
        self._configs = {c.facility_id: c for c in (configs or [])}

    def get_configs(
        self, org_id: str, facility_ids: list[str] | None = None
    ) -> list[FacilityConfig]:
        if facility_ids is None:
            return [c for c in self._configs.values() if c.org_id == org_id]
        return [
            self._configs[fid]
            for fid in facility_ids
            if fid in self._configs and self._configs[fid].org_id == org_id
        ]


class FakeShiftRetriever(IShiftRetriever):
    """InMemory implementation of IShiftRetriever for testing."""

    def __init__(self, shifts: list[Shift] | None = None):
        self._shifts = shifts or []

    def get_shifts_for_org(
        self, org_id: str, facility_timezones: dict[str, str]
    ) -> list[Shift]:
        # Simple filtering. In real implementation, this might hydrate timezones.
        return [s for s in self._shifts if s.org_id == org_id]

    def get_shifts_by_keys(
        self,
        shift_keys: list[ShiftKey],
        facility_timezones: dict[str, str],
        org_id: str,
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


class OptimizerTestBuilder:
    def __init__(self) -> None:
        # 1. DATA DEFAULTS (Empty/Safe Defaults)
        self._employees: list[Employee] = []
        self._nurses: list[NurseProfile] = []
        self._comp_records: list[StaffCompensationRecord] = []
        self._accumulated_hours: dict[str, float] = {}
        self._preference_penalties: dict[str, float] = {}
        self._stored_schedules: dict[tuple[str, str], Schedule] = {}
        self._acuity_data: list[ResidentAcuity] = []
        self._shifts: list[Shift] = []
        self._facility_configs: list[FacilityConfig] = []

        # 2. LOGIC DEFAULTS (The "Standard" Configuration)
        self._hprd_calculator: IHprdRequirementCalculator | None = None

        # Default Strategies
        self._global_pay_strategies: list[IPayModelStrategy] | None = None
        self._facility_constraint_strategies: list[
            IFacilityScopedConstraintStrategy
        ] = [HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl())]
        self._facility_rule_strategies: list[IFacilityScopedConstraintStrategy] = []
        self._penalty_strategies: list[
            IObjectivePenaltyStrategy
        ] = []  # Set in build() if not overridden

        # 3. EXPOSED ARTIFACTS (Available after build/solve)
        self.pay_processor: ShiftPayProcessor | None = None
        self.created_provider: IScenarioDataProvider | None = None
        self._factory: ScenarioDataProviderFactory | None = None

    @property
    def factory(self) -> ScenarioDataProviderFactory:
        if self._factory is None:
            raise ValueError(
                "Factory has not been built yet. Call build_optimizer() first."
            )
        return self._factory

    # --- FLUENT CONFIGURATION METHODS ---

    def with_employees(
        self,
        employees: list[Employee],
        nurses: list[NurseProfile],
    ) -> OptimizerTestBuilder:
        self._employees = employees
        self._nurses = nurses
        return self

    def with_financials(
        self,
        records: list[StaffCompensationRecord],
    ) -> OptimizerTestBuilder:
        self._comp_records = records
        return self

    def with_history(self, hours_map: dict[str, float]) -> OptimizerTestBuilder:
        self._accumulated_hours = hours_map
        return self

    def with_preference_penalties(
        self,
        penalties: dict[str, float],
    ) -> OptimizerTestBuilder:
        self._preference_penalties = penalties
        return self

    def with_schedule(
        self, schedule: Schedule, schedule_id: str, org_id: str
    ) -> OptimizerTestBuilder:
        """Pre-loads a schedule into the mock database for retrieval."""
        self._stored_schedules[(schedule_id, org_id)] = schedule
        return self

    def with_hprd_calculator(
        self,
        calculator: IHprdRequirementCalculator,
    ) -> OptimizerTestBuilder:
        """Override the default HPRD logic with a specific Fake or Mock."""
        self._hprd_calculator = calculator
        return self

    def with_strategies(
        self,
        pay: list[IPayModelStrategy] | None = None,
        constraints: list[IFacilityScopedConstraintStrategy] | None = None,
    ) -> OptimizerTestBuilder:
        """Allows swapping out entire strategy lists."""
        if pay is not None:
            self._global_pay_strategies = pay
        if constraints is not None:
            self._facility_constraint_strategies = constraints
        return self

    def with_acuity_data(self, data: list[ResidentAcuity]) -> OptimizerTestBuilder:
        self._acuity_data = data
        return self

    # --- THE BUILD METHOD ---

    def build_optimizer(self) -> NurseShiftScheduleOptimizer:
        # 1. Instantiate Fakes using the accumulated state
        fake_emp_retriever = FakeEmployeeRetriever(self._employees)
        fake_nurse_retriever = FakeNurseRetriever(self._nurses)
        fake_comp_service = FakeStaffCompensationService(self._comp_records)
        fake_history_service = FakeWorkHistoryService(self._accumulated_hours)

        # Default ML Fake (Can add a .with_ml_scores() method if needed)
        fake_ml_retriever = FakeMLModelRetriever(
            MlModelOutputs(
                turnover_risk_scores={},
                shift_call_out_forecast=0.0,
                unit_acuity_stress={},
                team_compatibility_scores={},
            )
        )

        fake_pref_processor = FakePreferencePenaltyProcessor(self._preference_penalties)

        # 2. Resolve HPRD Logic (Use provided override OR construct default)
        if self._hprd_calculator:
            hprd_calc = self._hprd_calculator
        else:
            # Construct the default "Zero/Passthrough" calculator
            fake_acuity_retriever = ResidentAcuityPerShiftRetrieverImpl(
                self._acuity_data
            )

            fake_req_retriever = FakeShiftRequirementsRetriever(
                default_requirements=ShiftSpecificRequirements(
                    target_hprd_rn=0.0,
                    target_hprd_cna=0.0,
                    target_total_hprd=0.0,
                )
            )
            hprd_calc = HprdRequirementCalculatorImpl(
                fake_acuity_retriever,
                fake_req_retriever,
            )

        # 3. Construct ShiftPayProcessor (The Logic Core)
        # We use a real Slicer and a mocked Rate Calculator for simplicity

        mock_eligibility = MagicMock()
        mock_eligibility.get_applicable_rules.return_value = (
            [],
            [],
        )  # No diffs/OT rules by default

        self.pay_processor = ShiftPayProcessor(
            eligibility_service=mock_eligibility,
            slicer=TimeOverlapShiftSlicer(),
            compensation_service=fake_comp_service,
        )

        # 4. Handle Default Strategies (Using the Processor)
        global_pay_strategies = self._global_pay_strategies
        if global_pay_strategies is None:
            global_pay_strategies = [
                WeeklyVolumePayStrategy(
                    shift_pay_processor=self.pay_processor, threshold=40.0
                )
            ]

        facility_constraint_strategies = self._facility_constraint_strategies
        if facility_constraint_strategies is None:
            facility_constraint_strategies = [
                HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl())
            ]

        penalty_strategies = self._penalty_strategies
        if not penalty_strategies:
            penalty_strategies = [
                QualityOfLifeStrategy(
                    preference_processor=fake_pref_processor,
                    nurse_retriever=fake_nurse_retriever,
                    employee_retriever=fake_emp_retriever,
                )
            ]

        # 5. Create Factory (Needed by Facade)
        self._factory = ScenarioDataProviderFactory(
            employee_retriever=fake_emp_retriever,
            nurse_retriever=fake_nurse_retriever,
            hprd_calculator=hprd_calc,
            staff_compensation_service=fake_comp_service,
            ml_model_retriever=fake_ml_retriever,
            work_history_service=fake_history_service,
        )

        # 5b. Patch Factory to act as Spy and inject History Logic
        hours_snapshot = self._accumulated_hours
        original_create = self._factory.create

        def side_effect_create(*args: Any, **kwargs: Any) -> IScenarioDataProvider:
            provider = original_create(*args, **kwargs)
            setattr(
                provider,
                "get_accumulated_hours_for_pay_period",
                lambda emp_id: hours_snapshot.get(emp_id, 0.0),
            )

            # Spy: Capture provider
            self.created_provider = provider
            return provider

        setattr(  # noqa: B010
            self._factory,
            "create",
            side_effect_create,
        )

        # 6. Instantiate Optimizer
        return NurseShiftScheduleOptimizer(
            core_variable_strategy=CoreVariableGenerationStrategy(),
            global_pay_strategies=global_pay_strategies,
            facility_constraint_strategies=facility_constraint_strategies,
            facility_rule_strategies=self._facility_rule_strategies,
            penalty_strategies=penalty_strategies,
        )

    def build_facade(self) -> WorkforceSchedulerService:
        """Helper to assemble the full application layer for testing."""
        optimizer = self.build_optimizer()

        # We know build() populates these
        assert self.pay_processor is not None
        assert self._factory is not None

        evaluator = ScheduleCostEvaluator(self.pay_processor)

        # Instantiate the Fake Retriever with any schedules configured in the builder
        fake_schedule_retriever = FakeScheduleRetriever(self._stored_schedules)
        fake_facility_repo = FakeFacilityRepository(self._facility_configs)
        fake_shift_retriever = FakeShiftRetriever(self._shifts)

        return WorkforceSchedulerService(
            provider_factory=self._factory,
            optimizer=optimizer,
            cost_evaluator=evaluator,
            schedule_retriever=fake_schedule_retriever,
            facility_repository=fake_facility_repo,
            shift_retriever=fake_shift_retriever,
        )
