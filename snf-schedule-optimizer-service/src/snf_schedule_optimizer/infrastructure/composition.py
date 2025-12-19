from sqlalchemy.orm import sessionmaker

from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.persistence.history_retriever import SQLARawHistoryRetriever
from snf_schedule_optimizer.persistence.schedule_retriever import (
    SQLAlchemyScheduleRetriever,
)
from snf_schedule_optimizer.persistence.shift_retriever import SQLAlchemyShiftRetriever
from snf_schedule_optimizer.services.payroll.calculations.schedule_cost_evaluator import (
    ScheduleCostEvaluator,
)
from snf_schedule_optimizer.services.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.services.scheduling.scheduler_facade import (
    WorkforceSchedulerService,
)


def compose_scheduler_service(
    session_factory: sessionmaker,
) -> WorkforceSchedulerService:
    """
    The 'Composition Root' helper.
    Wires up the Hexagon by connecting Infrastructure Adapters to Domain Ports.
    """
    # Note: We create a temporary session just to satisfy the construction
    # if the retrievers don't handle session scoping themselves.
    # Ideally, repositories accept a session or a factory.
    db = session_factory()

    # 1. Infrastructure Adapters (Persistence)
    shift_retriever = SQLAlchemyShiftRetriever(db)
    schedule_retriever = SQLAlchemyScheduleRetriever(db)
    facility_repo = SQLAlchemyFacilityRepository(db)
    history_retriever = SQLARawHistoryRetriever(db)

    # 2. Domain Services / Providers
    # (Assuming other required retrievers for the factory exist)
    provider_factory = ScenarioDataProviderFactory(
        employee_retriever=...,  # Inject impls
        nurse_retriever=...,
        hprd_calculator=...,
        staff_compensation_service=...,
        ml_model_retriever=...,
        work_history_service=...,  # Usually wires to history_retriever
    )

    # 3. Optimizer & Costing Engine
    optimizer = NurseShiftScheduleOptimizer(...)
    pay_processor = ShiftPayProcessor(...)
    cost_evaluator = ScheduleCostEvaluator(pay_processor)

    # 4. Application Facade
    return WorkforceSchedulerService(
        provider_factory=provider_factory,
        optimizer=optimizer,
        cost_evaluator=cost_evaluator,
        schedule_retriever=schedule_retriever,
        facility_repository=facility_repo,
        shift_retriever=shift_retriever,
    )
