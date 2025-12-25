from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import (
    Differential,
    DifferentialDateInterval,
    DifferentialType,
    DomainPrimaryKeyType,
    OvertimeTrigger,
    Shift,
)
from snf_schedule_optimizer.models.persistence_dtos import (
    DifferentialRuleData,
    OvertimeRuleData,
)
from snf_schedule_optimizer.services.payroll.interfaces import (
    IDifferentialRule,
    IDifferentialRuleRepo,
    IOvertimeRule,
    IOvertimeRuleRepo,
)
from snf_schedule_optimizer.sqlalchemy_models.differential_rule import (
    DifferentialRuleModel,
)
from snf_schedule_optimizer.sqlalchemy_models.overtime_rule import OvertimeRuleModel

# --- Assumed Interfaces & Models ---
# Assuming these interfaces and models are available:
# IDifferentialRule, IOvertimeRule (with priority, applicable_job_titles, etc.)
# DailyPatternDifferentialRule, ThresholdOvertimeRule (concrete rules)
# Employee, Shift, OvertimeTrigger

# --- CONCRETE TEST RULES (Minimal Implementation) ---


class MockDifferentialRule(IDifferentialRule):
    """A concrete differential rule used solely for testing retrieval/slicing."""

    def __init__(self, name: str, rate: float, priority: int, job_titles: list[str]):
        self._name = name
        self._rate = rate
        self._priority = priority
        self._job_titles = job_titles
        self._differential = Differential(
            "diff_test_1", DifferentialType.MULTIPLIER, 10, None
        )

    # Required by IDifferentialRule (must be implemented concretely)
    @property
    def differential(self) -> Differential:
        return self._differential

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def applicable_job_titles(self) -> list[str] | None:
        return self._job_titles

    @property
    def required_certifications(self) -> list[str] | None:
        return None

    @property
    def certification_match_type(self) -> str:
        return "ALL"

    def get_applicable_intervals_for_shift(
        self, shift: Shift
    ) -> list[DifferentialDateInterval]:
        # Placeholder for slicing logic
        return []


class MockOvertimeRule(IOvertimeRule):
    """A concrete OT rule used solely for testing retrieval/calculation."""

    def __init__(
        self,
        name: str,
        multiplier: float,
        priority: int,
        trigger: OvertimeTrigger,
        contract_id: DomainPrimaryKeyType | None = None,
    ):
        self._name = name
        self._multiplier = multiplier
        self._priority = priority
        self._trigger = trigger
        self._contract_id = contract_id

    @property
    def multiplier(self) -> float:
        return self._multiplier

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def trigger(self) -> OvertimeTrigger:
        return self._trigger

    # Required by RuleEligibilityCriteria
    @property
    def applicable_job_titles(self) -> list[str] | None:
        return None

    @property
    def required_certifications(self) -> list[str] | None:
        return None

    @property
    def certification_match_type(self) -> str:
        return "ALL"

    @property
    def contract_id(self) -> DomainPrimaryKeyType | None:
        return self._contract_id


class SQLDifferentialRuleRepo(IDifferentialRuleRepo):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_rules(
        self, org_id: DomainPrimaryKeyType
    ) -> list[DifferentialRuleData]:
        stmt = select(DifferentialRuleModel).where(
            DifferentialRuleModel.org_id == org_id
        )
        result: Sequence[DifferentialRuleModel] = (
            await self.session.scalars(stmt)
        ).all()

        return [m.to_domain() for m in result]


class SQLOvertimeRuleRepo(IOvertimeRuleRepo):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_rules(
        self, org_id: DomainPrimaryKeyType
    ) -> list[OvertimeRuleData]:
        stmt = select(OvertimeRuleModel).where(OvertimeRuleModel.org_id == org_id)
        result: Sequence[OvertimeRuleModel] = (await self.session.scalars(stmt)).all()
        return [m.to_domain() for m in result]
