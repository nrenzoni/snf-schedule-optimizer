from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from snf_schedule_optimizer.ml_output_retrievers import MLModelOutputsRetrieverImpl
from snf_schedule_optimizer.optimizer.calculators import (
    HprdRequirementCalculatorImpl,
    NurseHardBlockCheckerImpl,
)

# Optimizer Core & Providers
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    HprdStaffingConstraintStrategy,
)
from snf_schedule_optimizer.optimizer.strategies.pay import WeeklyVolumePayStrategy
from snf_schedule_optimizer.optimizer.strategies.penalties import QualityOfLifeStrategy

# Strategies
from snf_schedule_optimizer.optimizer.strategies.variables import (
    CoreVariableGenerationStrategy,
)
from snf_schedule_optimizer.persistence import (
    SQLCertificationService,
    SQLNurseRetriever,
    SQLShiftRequirementsRetriever,
)
from snf_schedule_optimizer.persistence.employee_retriever import (
    SQLEmployeeRetriever,
)
from snf_schedule_optimizer.persistence.employee_rule_retriever import (
    SQLEmployeeRulesRetriever,
)
from snf_schedule_optimizer.persistence.facility_retriever import SQLFacilityRetriever
from snf_schedule_optimizer.persistence.facility_rules_retriever import (
    SQLFacilityRulesRetriever,
)

# Persistence Implementations
from snf_schedule_optimizer.persistence.history_retriever import SQLRawHistoryRetriever
from snf_schedule_optimizer.persistence.resident_acuity_per_shift_retriever import (
    SQLResidentAcuityPerShiftRetriever,
)
from snf_schedule_optimizer.persistence.schedule_retriever import (
    SQLScheduleRetriever,
)
from snf_schedule_optimizer.persistence.shift_retriever import SQLShiftRetriever
from snf_schedule_optimizer.persistence.staff_compensation_retriever import (
    SQLStaffCompensationRetriever,
)
from snf_schedule_optimizer.resident_acuity_retrievers import (
    ResidentAcuityPerShiftRetrieverImpl,
)
from snf_schedule_optimizer.services.payroll.calculations.facility_rules_service import (
    FacilityRulesService,
)
from snf_schedule_optimizer.services.payroll.calculations.schedule_cost_evaluator import (
    ScheduleCostEvaluator,
)
from snf_schedule_optimizer.services.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.services.payroll.calculations.shift_slicers import (
    TimeOverlapShiftSlicer,
)
from snf_schedule_optimizer.services.payroll.rules.rule_eligibility_service import (
    RuleEligibilityService,
)
from snf_schedule_optimizer.services.scheduling.processors.preference_penalty_processor import (
    PreferencePenaltyProcessorImpl,
)

# Services
from snf_schedule_optimizer.services.scheduling.scheduler_facade import (
    WorkforceSchedulerService,
)
from snf_schedule_optimizer.services.timekeeping.shift_reconciliation import (
    ShiftReconcilerService,
)
from snf_schedule_optimizer.services.timekeeping.work_history_service import (
    EmployeeWorkHistoryServiceImpl,
)


def compose_scheduler_service(
    session_factory: async_sessionmaker[AsyncSession],
) -> WorkforceSchedulerService:
    """
    The 'Composition Root' helper.
    Wires up the Hexagon by connecting Infrastructure Adapters to Domain Ports.
    """
    # Create a database session for the duration of the service construction
    db: AsyncSession = session_factory()

    # 1. Low-Level Infrastructure Adapters (Persistence)
    shift_retriever = SQLShiftRetriever(db)
    schedule_retriever = SQLScheduleRetriever(db)
    facility_retriever = SQLFacilityRetriever(db)
    history_retriever = SQLRawHistoryRetriever(db)
    employee_retriever = SQLEmployeeRetriever(db)
    nurse_retriever = SQLNurseRetriever(db)
    compensation_repo = SQLStaffCompensationRetriever(db)

    # 2. Specialized Domain Data Access
    shift_req_retriever = SQLShiftRequirementsRetriever(db)
    acuity_retriever = SQLResidentAcuityPerShiftRetriever(db)

    ml_retriever = (
        MLModelOutputsRetrieverImpl()
    )  # Assuming no DB dependency for ML client

    # 3. Calculation Services
    hprd_calculator = HprdRequirementCalculatorImpl(
        resident_acuity_retriever=acuity_retriever,
        shift_requirements_retriever=shift_req_retriever,
    )

    facility_rule_retriever = SQLFacilityRulesRetriever(db)
    employee_rule_retriever = SQLEmployeeRulesRetriever(db)

    facility_rules_service = FacilityRulesService(
        facility_rule_retriever=facility_rule_retriever,
        employee_rule_retriever=employee_rule_retriever,
    )

    shift_reconciler = ShiftReconcilerService(
        facility_rules_service=facility_rules_service,
    )
    work_history_service = EmployeeWorkHistoryServiceImpl(
        history_retriever=history_retriever,
        shift_retriever=shift_retriever,
        facility_config_retriever=facility_retriever,
        shift_reconciler=shift_reconciler,
    )

    # 4. Payroll & Costing Logic
    # (Assuming a simple eligibility service for now or mock it)
    certification_service = SQLCertificationService(db)

    rule_eligibility_service = RuleEligibilityService(
        certification_service=certification_service,
        rule_retriever_service=...,
    )

    pay_processor = ShiftPayProcessor(
        eligibility_service=rule_eligibility_service,
        slicer=TimeOverlapShiftSlicer(),
        compensation_service=compensation_repo,
    )
    cost_evaluator = ScheduleCostEvaluator(pay_processor)

    # 5. Optimization Strategies
    penalty_processor = PreferencePenaltyProcessorImpl(
        staff_compensation_retriever=compensation_repo,
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[WeeklyVolumePayStrategy(pay_processor, threshold=40.0)],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl())
        ],
        facility_rule_strategies=[],
        penalty_strategies=[
            QualityOfLifeStrategy(
                preference_processor=penalty_processor,
                nurse_retriever=nurse_retriever,
                employee_retriever=employee_retriever,
            )
        ],
    )

    # 6. Data Provider Factory (Scoped context builder)
    provider_factory = ScenarioDataProviderFactory(
        employee_retriever=employee_retriever,
        nurse_retriever=nurse_retriever,
        hprd_calculator=hprd_calculator,
        staff_compensation_service=compensation_repo,
        ml_model_retriever=ml_retriever,
        work_history_service=work_history_service,
    )

    # 7. Application Facade (Main Entry Point)
    return WorkforceSchedulerService(
        provider_factory=provider_factory,
        optimizer=optimizer,
        cost_evaluator=cost_evaluator,
        schedule_retriever=schedule_retriever,
        facility_repository=facility_retriever,
        shift_retriever=shift_retriever,
    )
