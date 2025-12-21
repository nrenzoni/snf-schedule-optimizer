from snf_schedule_optimizer.models import Employee, Shift
from snf_schedule_optimizer.services.payroll.interfaces import (
    IDifferentialRule,
    IOvertimeRule,
    IRuleRetrievalService,
)
from snf_schedule_optimizer.services.payroll.rules.shift_rules import (
    DailyPatternDifferentialRule,
)


class RuleRetrievalService(IRuleRetrievalService):
    """
    DOMAIN SERVICE: Coordinates retrievers and applies matching/filtering logic.
    """

    def __init__(
        self,
        diff_retriever: IDifferentialRuleRetriever,
        ot_retriever: IOvertimeRuleRetriever,
    ):
        self.diff_retriever = diff_retriever
        self.ot_retriever = ot_retriever

    async def get_differential_rules_by_context(
        self, employee: Employee, shift: Shift
    ) -> list[IDifferentialRule]:
        # 1. Fetch raw data for the Org
        dtos = await self.diff_retriever.get_all_rules(shift.org_id)

        # 2. Filter by business logic
        return [
            DailyPatternDifferentialRule(d)
            for d in dtos
            if self._is_eligible(d, employee)
        ]

    async def get_overtime_rules_by_context(
        self, employee: Employee, shift: Shift
    ) -> list[IOvertimeRule]:
        dtos = await self.ot_retriever.get_all_rules(shift.org_id)

        return [PayrollOvertimeRule(d) for d in dtos if self._is_eligible(d, employee)]

    def _is_eligible(self, rule_dto: Any, employee: Employee) -> bool:
        """Centralized eligibility logic for all payroll rules."""
        if (
            rule_dto.applicable_job_titles
            and employee.job_title not in rule_dto.applicable_job_titles
        ):
            return False

        # Future: Add union contract matching here
        # if rule_dto.contract_id and employee.contract_id != rule_dto.contract_id:
        #    return False

        return True
