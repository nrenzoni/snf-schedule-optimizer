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
from snf_schedule_optimizer.persistence.employee_retriever import (
    SQLEmployeeRetriever,
)
from snf_schedule_optimizer.persistence.facility_repository import (
    SQLAlchemyFacilityRepository,
)

# Persistence Implementations
from snf_schedule_optimizer.persistence.history_retriever import SQLARawHistoryRetriever
from snf_schedule_optimizer.persistence.nurse_retrievers import SQLANurseRetriever
from snf_schedule_optimizer.persistence.schedule_retriever import (
    SQLAlchemyScheduleRetriever,
)
from snf_schedule_optimizer.persistence.shift_requirements_retriever import (
    SQLAShiftRequirementsRetriever,
)
from snf_schedule_optimizer.persistence.shift_retriever import SQLAlchemyShiftRetriever
from snf_schedule_optimizer.persistence.staff_compensation_service import (
    SQLAStaffCompensationService,
)
from snf_schedule_optimizer.resident_acuity_retrievers import (
    ResidentAcuityPerShiftRetrieverImpl,
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
    ShiftReconcilerServiceImpl,
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
    shift_retriever = SQLAlchemyShiftRetriever(db)
    schedule_retriever = SQLAlchemyScheduleRetriever(db)
    facility_repo = SQLAlchemyFacilityRepository(db)
    history_retriever = SQLARawHistoryRetriever(db)
    employee_retriever = SQLEmployeeRetriever(db)
    nurse_retriever = SQLANurseRetriever(db)
    compensation_repo = SQLAStaffCompensationService(db)

    # 2. Specialized Domain Data Access
    shift_req_retriever = SQLAShiftRequirementsRetriever(db)
    acuity_retriever = ResidentAcuityPerShiftRetrieverImpl(db)
    ml_retriever = (
        MLModelOutputsRetrieverImpl()
    )  # Assuming no DB dependency for ML client

    # 3. Calculation Services
    hprd_calculator = HprdRequirementCalculatorImpl(
        resident_acuity_retriever=acuity_retriever,
        shift_requirements_retriever=shift_req_retriever,
    )

    shift_reconciler = ShiftReconcilerServiceImpl(
        facility_rules_service=...,
    )
    work_history_service = EmployeeWorkHistoryServiceImpl(
        history_retriever=history_retriever,
        shift_retriever=shift_retriever,
        facility_config_repo=facility_repo,
        shift_reconciler=shift_reconciler,
    )

    # 4. Payroll & Costing Logic
    # (Assuming a simple eligibility service for now or mock it)
    rule_eligibility_service = RuleEligibilityService(
        certification_service=..., rule_retriever_service=...
    )

    pay_processor = ShiftPayProcessor(
        eligibility_service=rule_eligibility_service,
        slicer=TimeOverlapShiftSlicer(),
        compensation_service=compensation_repo,
    )
    cost_evaluator = ScheduleCostEvaluator(pay_processor)

    # 5. Optimization Strategies
    penalty_processor = PreferencePenaltyProcessorImpl(
        staff_compensation_service=...,
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
        facility_repository=facility_repo,
        shift_retriever=shift_retriever,
    )
