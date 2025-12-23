from typing import Any

from snf_schedule_optimizer.models import (
    Employee,
    OvertimeTrigger,
    Shift,
)
from snf_schedule_optimizer.models.persistence_dtos import OvertimeRuleData
from snf_schedule_optimizer.services.payroll.calculations.overtime_calculation import (
    ThresholdOvertimeRule,
)
from snf_schedule_optimizer.services.payroll.interfaces import (
    IDifferentialRule,
    IDifferentialRuleRepo,
    IOvertimeRule,
    IOvertimeRuleRepo,
    IRuleRetrievalService,
)
from snf_schedule_optimizer.services.payroll.rules.shift_rules import (
    PatternDifferentialRule,
)


class RuleRetrievalService(IRuleRetrievalService):
    """
    DOMAIN SERVICE: Coordinates retrievers and applies matching/filtering logic.
    """

    def __init__(
        self,
        diff_retriever: IDifferentialRuleRepo,
        ot_retriever: IOvertimeRuleRepo,
    ):
        self.diff_retriever = diff_retriever
        self.ot_retriever = ot_retriever

    async def get_differential_rules_by_context(
        self, employee: Employee, shift: Shift
    ) -> list[IDifferentialRule]:
        # 1. Fetch raw data for the Org
        data_list = await self.diff_retriever.get_all_rules(shift.org_id)
        return [
            PatternDifferentialRule(d)
            for d in data_list
            if self._is_eligible(d, employee)
        ]

    async def get_overtime_rules_by_context(
        self, employee: Employee, shift: Shift
    ) -> list[IOvertimeRule]:
        """
        Refactored to map Data DTOs to specific domain ThresholdOvertimeRule objects.
        """
        data_list = await self.ot_retriever.get_all_rules(shift.org_id)

        rules: list[IOvertimeRule] = []
        for d in data_list:
            if self._is_eligible(d, employee):
                rules.append(self._map_to_threshold_rule(d))

        return rules

    def _map_to_threshold_rule(self, d: OvertimeRuleData) -> ThresholdOvertimeRule:
        """
        Factory method to construct the domain trigger and rule.
        """

        trigger = OvertimeTrigger(
            trigger_type=d.trigger_type,
            daily_threshold=d.daily_threshold,
            weekly_threshold=d.weekly_threshold,
            consecutive_day_threshold=d.consecutive_day_threshold,
            consecutive_hours_threshold=d.consecutive_hours_threshold,
            work_period_start_day=d.work_period_start_day,
            work_period_start_time=d.work_period_start_time,
            daily_period_reset_time=d.daily_period_reset_time,
            days_of_week_trigger=d.days_of_week_trigger,
        )

        return ThresholdOvertimeRule(
            name=d.description,
            multiplier=d.multiplier,
            trigger=trigger,
            priority=d.priority,
            applicable_job_titles=d.applicable_job_titles,
            required_certifications=d.required_certifications,
            certification_match_type=d.certification_match_type,
            contract_id=d.contract_id,
        )

    def _is_eligible(self, rule_data: Any, employee: Employee) -> bool:
        """Centralized eligibility logic for all payroll rules."""
        if (  # noqa: SIM103
            rule_data.applicable_job_titles
            and employee.job_title not in rule_data.applicable_job_titles
        ):
            return False

        # Certification checks could be added here
        # ...

        return True
