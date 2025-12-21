from collections.abc import AsyncGenerator
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from that_depends import BaseContainer, Provide
from that_depends.providers import Factory, Resource

from snf_schedule_optimizer.ml_output_retrievers import MLModelOutputsRetrieverImpl
from snf_schedule_optimizer.optimizer.calculators import (
    HprdRequirementCalculator,
    NurseHardBlockCheckerImpl,
)

# Optimizer Core & Providers
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    IObjectivePenaltyStrategy,
    IPayModelStrategy,
)
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
    SQLDifferentialRuleRetriever,
    SQLNurseRetriever,
    SQLOvertimeRuleRetriever,
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
from snf_schedule_optimizer.services.payroll.calculations.facility_rules_service import (
    FacilityRulesService,
)
from snf_schedule_optimizer.services.payroll.calculations.rule_retrieval_service import (
    RuleRetrievalService,
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


async def compose_scheduler_service(
    session_factory: async_sessionmaker[AsyncSession],
) -> "WorkforceSchedulerService":
    """
    Composition root that uses `that-depends` providers to wire infra -> domain.
    """

    # async resource factory that yields a session (ensures proper enter/exit)
    async def _make_session() -> AsyncGenerator[AsyncSession, Any]:
        async with session_factory() as sess:
            yield sess

    class SchedulerContainer(BaseContainer):
        # scoped async DB session
        db_session = Resource(_make_session)

        # 1. Low-Level Infrastructure Adapters (Persistence)
        shift_retriever = Factory(
            SQLShiftRetriever,
            session=Provide[db_session],
        )
        schedule_retriever = Factory(
            SQLScheduleRetriever,
            db_session=Provide[db_session],
        )
        facility_retriever = Factory(
            SQLFacilityRetriever,
            session=Provide[db_session],
        )
        history_retriever = Factory(
            SQLRawHistoryRetriever,
            db_session=Provide[db_session],
        )
        employee_retriever = Factory(
            SQLEmployeeRetriever,
            db_session=Provide[db_session],
        )
        nurse_retriever = Factory(
            SQLNurseRetriever,
            session=Provide[db_session],
        )
        compensation_retriever = Factory(
            SQLStaffCompensationRetriever,
            db_session=Provide[db_session],
        )

        # 2. Specialized Domain Data Access
        shift_req_retriever = Factory(
            SQLShiftRequirementsRetriever,
            db_session=Provide[db_session],
        )
        acuity_retriever = Factory(
            SQLResidentAcuityPerShiftRetriever,
            db_session=Provide[db_session],
        )
        ml_retriever = Factory(MLModelOutputsRetrieverImpl)  # no-db client

        # 3. Calculation Services
        hprd_calculator = Factory(
            HprdRequirementCalculator,
            resident_acuity_retriever=Provide[acuity_retriever],
            shift_requirements_retriever=Provide[shift_req_retriever],
        )

        facility_rule_retriever = Factory(
            SQLFacilityRulesRetriever,
            db_session=Provide[db_session],
        )
        employee_rule_retriever = Factory(
            SQLEmployeeRulesRetriever,
            db_session=Provide[db_session],
        )

        facility_rules_service = Factory(
            FacilityRulesService,
            facility_rule_retriever=Provide[facility_rule_retriever],
            employee_rule_retriever=Provide[employee_rule_retriever],
        )

        shift_reconciler = Factory(
            ShiftReconcilerService,
            facility_rules_service=Provide[facility_rules_service],
        )

        work_history_service = Factory(
            EmployeeWorkHistoryServiceImpl,
            history_retriever=Provide[history_retriever],
            shift_retriever=Provide[shift_retriever],
            facility_config_retriever=Provide[facility_retriever],
            shift_reconciler=Provide[shift_reconciler],
        )

        # 4. Payroll & Costing Logic
        certification_service = Factory(
            SQLCertificationService,
            db_session=Provide[db_session],
        )
        sql_differential_rule_retriever = Factory(
            SQLDifferentialRuleRetriever, session=Provide[db_session]
        )
        sql_overtime_rule_retriever = Factory(
            SQLOvertimeRuleRetriever, session=Provide[db_session]
        )

        rule_retriever_service = Factory(
            RuleRetrievalService,
            diff_retriever=Provide[sql_differential_rule_retriever],
            ot_retriever=Provide[sql_overtime_rule_retriever],
        )

        rule_eligibility_service = Factory(
            RuleEligibilityService,
            certification_service=Provide[certification_service],
            rule_retriever_service=Provide[rule_retriever_service],
        )

        slicer = Factory(TimeOverlapShiftSlicer)

        pay_processor = Factory(
            ShiftPayProcessor,
            eligibility_service=Provide[rule_eligibility_service],
            slicer=Provide[slicer],
            compensation_service=Provide[compensation_retriever],
        )

        cost_evaluator = Factory(
            ScheduleCostEvaluator,
            shift_pay_processor=Provide[pay_processor],
        )

        # 5. Optimization Strategies
        penalty_processor = Factory(
            PreferencePenaltyProcessorImpl,
            staff_compensation_retriever=Provide[compensation_retriever],
        )

        core_variable_strategy = Factory(CoreVariableGenerationStrategy)

        # single-item strategy providers wrapped to produce lists expected by optimizer
        weekly_pay_strategy_list = Factory(
            lambda pp: cast(
                list[IPayModelStrategy],
                [WeeklyVolumePayStrategy(pp, threshold=40.0)],
            ),
            Provide[pay_processor],
        )
        nurse_hard_block_checker = Factory(NurseHardBlockCheckerImpl)
        facility_constraint_strategies_list = Factory(
            lambda checker: cast(
                list[IFacilityScopedConstraintStrategy],
                [HprdStaffingConstraintStrategy(checker)],
            ),
            Provide[nurse_hard_block_checker],
        )

        facility_rule_strategies_list = Factory(
            lambda: cast(
                list[IFacilityScopedConstraintStrategy],
                [],
            )
        )  # placeholder empty list

        penalty_strategies_list = Factory(
            lambda pp, nr, er: cast(
                list[IObjectivePenaltyStrategy],
                [
                    QualityOfLifeStrategy(
                        preference_processor=pp,
                        nurse_retriever=nr,
                        employee_retriever=er,
                    )
                ],
            ),
            Provide[penalty_processor],
            Provide[nurse_retriever],
            Provide[employee_retriever],
        )

        optimizer = Factory(
            NurseShiftScheduleOptimizer,
            core_variable_strategy=Provide[core_variable_strategy],
            global_pay_strategies=Provide[weekly_pay_strategy_list],
            facility_constraint_strategies=Provide[facility_constraint_strategies_list],
            facility_rule_strategies=Provide[facility_rule_strategies_list],
            penalty_strategies=Provide[penalty_strategies_list],
        )

        # 6. Data Provider Factory (Scoped context builder)
        provider_factory = Factory(
            ScenarioDataProviderFactory,
            employee_retriever=Provide[employee_retriever],
            nurse_retriever=Provide[nurse_retriever],
            hprd_calculator=Provide[hprd_calculator],
            staff_compensation_service=Provide[compensation_retriever],
            ml_model_retriever=Provide[ml_retriever],
            work_history_service=Provide[work_history_service],
        )

        # 7. Application Facade (Main Entry Point)
        scheduler_service = Factory(
            WorkforceSchedulerService,
            provider_factory=Provide[provider_factory],
            optimizer=Provide[optimizer],
            cost_evaluator=Provide[cost_evaluator],
            schedule_retriever=Provide[schedule_retriever],
            facility_repository=Provide[facility_retriever],
            shift_retriever=Provide[shift_retriever],
        )

    return await SchedulerContainer.scheduler_service()
