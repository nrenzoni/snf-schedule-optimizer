from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from snf_schedule_optimizer.models import (
    Employee,
    MlModelOutputs,
    NurseProfile,
    ShiftSpecificRequirements,
    StaffCompensationRecord,
    WorkedShiftSegment,
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
from snf_schedule_optimizer.services.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.services.payroll.calculations.shift_slicers import (
    TimeOverlapShiftSlicer,
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


class OptimizerTestBuilder:
    def __init__(self) -> None:
        # 1. DATA DEFAULTS (Empty/Safe Defaults)
        self._employees: list[Employee] = []
        self._nurses: list[NurseProfile] = []
        self._comp_records: list[StaffCompensationRecord] = []
        self._accumulated_hours: dict[str, float] = {}
        self._preference_penalties: dict[str, float] = {}

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

    # --- THE BUILD METHOD ---

    def build(self) -> NurseShiftScheduleOptimizer:
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
            mock_acuity_retriever = MagicMock()
            mock_acuity_retriever.get_resident_acuity_list.return_value = []

            fake_req_retriever = FakeShiftRequirementsRetriever(
                default_requirements=ShiftSpecificRequirements(
                    target_hprd_rn=0.0,
                    target_hprd_cna=0.0,
                    target_total_hprd=0.0,
                )
            )
            hprd_calc = HprdRequirementCalculatorImpl(
                mock_acuity_retriever,
                fake_req_retriever,
            )

        # 3. Construct ShiftPayProcessor (The Logic Core)
        # We use a real Slicer and a mocked Rate Calculator for simplicity

        mock_eligibility = MagicMock()
        mock_eligibility.get_applicable_rules.return_value = (
            [],
            [],
        )  # No diffs/OT rules by default

        # Create a simple Rate Calculator that returns base_rate * duration
        # (This avoids needing the full DifferentialAndOvertimeRateCalculator implementation)
        mock_rate_calc = MagicMock()

        # We need this mock to return sensible data, otherwise costs are 0
        # This lambda mimics: cost = rate * hours
        # Note: This ignores differentials, but works for base testing
        # To strictly type this, we'd make a FakeRateCalculator class
        # But for brevity in the builder:
        def simple_rate_calc(
            record: StaffCompensationRecord,
            segment: WorkedShiftSegment,
        ) -> float:
            # Fallback to 0 if record missing
            rate = record.base_rate_effective if record else 0.0
            return rate * segment.duration_hours  # Return float cost

        mock_rate_calc.calculate_effective_rate.side_effect = simple_rate_calc

        self.pay_processor = ShiftPayProcessor(
            eligibility_service=mock_eligibility,
            slicer=TimeOverlapShiftSlicer(),
            rate_calculator=mock_rate_calc,
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

        # 5. Create Factory with Side Effects
        # We capture the current state of self._accumulated_hours in the closure
        factory = ScenarioDataProviderFactory(
            employee_retriever=fake_emp_retriever,
            nurse_retriever=fake_nurse_retriever,
            hprd_calculator=hprd_calc,
            staff_compensation_service=fake_comp_service,
            ml_model_retriever=fake_ml_retriever,
            work_history_service=fake_history_service,
        )

        hours_snapshot = self._accumulated_hours
        original_create = factory.create

        def side_effect_create(*args: Any, **kwargs: Any) -> IScenarioDataProvider:
            provider = original_create(*args, **kwargs)

            provider.get_accumulated_hours_for_pay_period = (
                lambda emp_id: hours_snapshot.get(emp_id, 0.0)
            )

            # Capture the provider instance for the test to use later
            self.created_provider = provider

            return provider

        factory.create = side_effect_create

        # 6. Instantiate Optimizer
        return NurseShiftScheduleOptimizer(
            provider_factory=factory,
            core_variable_strategy=CoreVariableGenerationStrategy(),
            global_pay_strategies=global_pay_strategies,
            facility_constraint_strategies=facility_constraint_strategies,
            facility_rule_strategies=self._facility_rule_strategies,
            penalty_strategies=penalty_strategies,
        )
