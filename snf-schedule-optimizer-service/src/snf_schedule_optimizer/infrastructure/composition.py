import abc
from collections.abc import AsyncGenerator
from typing import Any, ClassVar, cast

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from that_depends import BaseContainer, Provide
from that_depends.providers import AbstractProvider, Factory, Resource

from snf_schedule_optimizer.domain.hr.certification_service import (
    CertificationService,
)
from snf_schedule_optimizer.domain.hr.interfaces import (
    ICertificationRepo,
    IEmployeeRepo,
    IStaffCompensationRepo,
)
from snf_schedule_optimizer.domain.payroll.calculations.facility_rules_service import (
    FacilityRulesService,
)
from snf_schedule_optimizer.domain.payroll.calculations.rule_retrieval_service import (
    RuleRetrievalService,
)
from snf_schedule_optimizer.domain.payroll.calculations.schedule_cost_evaluator import (
    ScheduleCostEvaluator,
)
from snf_schedule_optimizer.domain.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.domain.payroll.calculations.shift_slicers import (
    TimeOverlapShiftSlicer,
)
from snf_schedule_optimizer.domain.payroll.interfaces import (
    IDifferentialRuleRepo,
    IEmployeeRulesRepo,
    IFacilityRulesRepo,
    IOvertimeRuleRepo,
)
from snf_schedule_optimizer.domain.payroll.rules.rule_eligibility_service import (
    RuleEligibilityService,
)
from snf_schedule_optimizer.domain.repositories import (
    IFacilityRepo,
    IShiftRepo,
)
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IScheduleRepo,
    IShiftRequirementsRepo,
)
from snf_schedule_optimizer.domain.scheduling.processors.preference_penalty_processor import (
    PreferencePenaltyProcessorImpl,
)
from snf_schedule_optimizer.domain.timekeeping.interfaces import IRawHistoryRepo
from snf_schedule_optimizer.domain.timekeeping.shift_reconciliation import (
    ShiftReconcilerService,
)
from snf_schedule_optimizer.domain.timekeeping.work_history_service import (
    EmployeeWorkHistoryServiceImpl,
)
from snf_schedule_optimizer.infrastructure.sqid_converter import IdObfuscator
from snf_schedule_optimizer.ml_output_repo import MLModelOutputsRepo
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
    INurseRepo,
    SQLCertificationRepo,
    SQLDifferentialRuleRepo,
    SQLNurseRepo,
    SQLOvertimeRuleRepo,
    SQLShiftRequirementsRepo,
)
from snf_schedule_optimizer.persistence.employee_repo import (
    SQLEmployeeRepo,
)
from snf_schedule_optimizer.persistence.employee_rule_repo import (
    SQLEmployeeRulesRepo,
)
from snf_schedule_optimizer.persistence.facility_repo import SQLFacilityRepo
from snf_schedule_optimizer.persistence.facility_rules_repo import (
    SQLFacilityRulesRepo,
)

# Persistence Implementations
from snf_schedule_optimizer.persistence.history_repo import SQLRawHistoryRepo
from snf_schedule_optimizer.persistence.resident_acuity_per_shift_repo import (
    SQLResidentAcuityPerShiftRepo,
)
from snf_schedule_optimizer.persistence.schedule_repo import (
    SQLScheduleRepo,
)
from snf_schedule_optimizer.persistence.shift_repo import SQLShiftRepo
from snf_schedule_optimizer.persistence.staff_compensation_repo import (
    SQLStaffCompensationRepo,
)
from snf_schedule_optimizer.resident_acuity_repo import (
    IResidentAcuityPerShiftRepo,
)
from snf_schedule_optimizer.service.facility.facility_facade import FacilityFacade

# Services
from snf_schedule_optimizer.service.scheduling.scheduler_facade import (
    WorkforceSchedulerFacade,
)


class IReposContainer(abc.ABC):
    """
    Port describing all persistence retrievers required by the application layer.

    This is a *container-level port*, not individual retriever ports.
    """

    # Core scheduling persistence
    shift_retriever: ClassVar[AbstractProvider[IShiftRepo]]
    schedule_retriever: ClassVar[AbstractProvider[IScheduleRepo]]
    facility_retriever: ClassVar[AbstractProvider[IFacilityRepo]]

    # Workforce & history
    certification_retriever: ClassVar[AbstractProvider[ICertificationRepo]]
    facility_rule_retriever: ClassVar[AbstractProvider[IFacilityRulesRepo]]
    employee_rule_retriever: ClassVar[AbstractProvider[IEmployeeRulesRepo]]
    differential_rule_retriever: ClassVar[AbstractProvider[IDifferentialRuleRepo]]
    overtime_rule_retriever: ClassVar[AbstractProvider[IOvertimeRuleRepo]]
    history_retriever: ClassVar[AbstractProvider[IRawHistoryRepo]]
    employee_retriever: ClassVar[AbstractProvider[IEmployeeRepo]]
    nurse_retriever: ClassVar[AbstractProvider[INurseRepo]]

    # Financials / rules
    compensation_retriever: ClassVar[AbstractProvider[IStaffCompensationRepo]]
    shift_req_retriever: ClassVar[AbstractProvider[IShiftRequirementsRepo]]
    acuity_retriever: ClassVar[AbstractProvider[IResidentAcuityPerShiftRepo]]

    db_engine: ClassVar[AbstractProvider[Engine]]
    db_session: ClassVar[AbstractProvider[AsyncSession]]


def build_repos_container(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> type["IReposContainer"]:
    async def _make_session() -> AsyncGenerator[AsyncSession, Any]:
        async with session_factory() as sess:
            yield sess

    class ReposContainer(BaseContainer, IReposContainer):
        db_session = Resource(_make_session)

        shift_retriever = Factory(
            SQLShiftRepo,
            session=Provide[db_session],
        )
        schedule_retriever = Factory(
            SQLScheduleRepo,
            db_session=Provide[db_session],
        )
        certification_retriever = Factory(
            SQLCertificationRepo,
            db_session=Provide[db_session],
        )
        overtime_rule_retriever = Factory(
            SQLOvertimeRuleRepo,
            session=Provide[db_session],
        )
        facility_rule_retriever = Factory(
            SQLFacilityRulesRepo,
            db_session=Provide[db_session],
        )
        employee_rule_retriever = Factory(
            SQLEmployeeRulesRepo,
            db_session=Provide[db_session],
        )
        differential_rule_retriever = Factory(
            SQLDifferentialRuleRepo,
            session=Provide[db_session],
        )
        facility_retriever = Factory(
            SQLFacilityRepo,
            session=Provide[db_session],
        )
        history_retriever = Factory(
            SQLRawHistoryRepo,
            db_session=Provide[db_session],
        )
        employee_retriever = Factory(
            SQLEmployeeRepo,
            db_session=Provide[db_session],
        )
        nurse_retriever = Factory(
            SQLNurseRepo,
            session=Provide[db_session],
        )
        compensation_retriever = Factory(
            SQLStaffCompensationRepo,
            db_session=Provide[db_session],
        )
        shift_req_retriever = Factory(
            SQLShiftRequirementsRepo,
            db_session=Provide[db_session],
        )
        acuity_retriever = Factory(
            SQLResidentAcuityPerShiftRepo,
            db_session=Provide[db_session],
        )

    return ReposContainer


class ISchedulerContainer(abc.ABC):
    """
    Port describing all application-level providers produced by SchedulerContainer.

    This is consumed only by composition roots.
    """

    # Core application facade
    scheduler_service: AbstractProvider[WorkforceSchedulerFacade]

    # (Optional but useful) Expose these if other entrypoints need them
    optimizer: AbstractProvider[NurseShiftScheduleOptimizer]
    provider_factory: AbstractProvider[ScenarioDataProviderFactory]
    cost_evaluator: AbstractProvider[ScheduleCostEvaluator]


def build_scheduler_container(
    retrievers: type[IReposContainer],
) -> type[ISchedulerContainer]:
    class SchedulerContainer(BaseContainer, ISchedulerContainer):
        # Import retrievers from the other container
        shift_retriever = retrievers.shift_retriever
        schedule_retriever = retrievers.schedule_retriever
        facility_rule_retriever = retrievers.facility_rule_retriever
        employee_rule_retriever = retrievers.employee_rule_retriever
        differential_rule_retriever = retrievers.differential_rule_retriever
        overtime_rule_retriever = retrievers.overtime_rule_retriever
        facility_retriever = retrievers.facility_retriever
        history_retriever = retrievers.history_retriever
        employee_retriever = retrievers.employee_retriever
        nurse_retriever = retrievers.nurse_retriever
        compensation_retriever = retrievers.compensation_retriever
        shift_req_retriever = retrievers.shift_req_retriever
        acuity_retriever = retrievers.acuity_retriever

        hprd_calculator = Factory(
            HprdRequirementCalculator,
            resident_acuity_retriever=Provide[acuity_retriever],
            shift_requirements_retriever=Provide[shift_req_retriever],
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

        ml_retriever = Factory(MLModelOutputsRepo)  # no-db client

        # domain / optimization wiring (unchanged)
        provider_factory = Factory(
            ScenarioDataProviderFactory,
            employee_retriever=Provide[employee_retriever],
            nurse_retriever=Provide[nurse_retriever],
            hprd_calculator=Provide[hprd_calculator],
            staff_compensation_service=Provide[compensation_retriever],
            ml_model_retriever=Provide[ml_retriever],
            work_history_service=Provide[work_history_service],
        )

        # 4. Payroll & Costing Logic
        certification_service = Factory(
            CertificationService,
            repo=Provide[retrievers.certification_retriever],
        )

        rule_retriever_service = Factory(
            RuleRetrievalService,
            diff_retriever=Provide[differential_rule_retriever],
            ot_retriever=Provide[overtime_rule_retriever],
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

        scheduler_service = Factory(
            WorkforceSchedulerFacade,
            provider_factory=Provide[provider_factory],
            optimizer=Provide[optimizer],
            cost_evaluator=Provide[cost_evaluator],
            schedule_retriever=Provide[schedule_retriever],
            facility_repository=Provide[facility_retriever],
            shift_retriever=Provide[shift_retriever],
        )

    return SchedulerContainer


class IFacilityContainer(abc.ABC):
    """
    Application services for the Facility subdomain.
    """

    facility_facade: AbstractProvider[FacilityFacade]
    facility_repo: AbstractProvider[IFacilityRepo]


def build_facility_container(
    retrievers_container: type[IReposContainer],
) -> type[IFacilityContainer]:
    class FacilityContainer(BaseContainer, IFacilityContainer):
        facility_repo = retrievers_container.facility_retriever

        facility_facade = Factory(
            FacilityFacade,
            facility_repo=Provide[facility_repo],
        )

    return FacilityContainer


class InfraContainer(BaseContainer):
    id_obfuscator = Factory(IdObfuscator)


def build_infra_container() -> type[InfraContainer]:
    return InfraContainer
