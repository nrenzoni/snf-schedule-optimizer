from typing import Protocol

import whenever

from snf_schedule_optimizer.models import Employee, Shift
from snf_schedule_optimizer.services.hr.interfaces import ICertificationService
from snf_schedule_optimizer.services.payroll.interfaces import (
    IDifferentialRule,
    IOvertimeRule,
    IRuleRetrievalService,
)


class RuleEligibilityCriteria(Protocol):
    """
    Protocol defining the minimum required properties for a rule object
    to be checked by the RuleEligibilityService.
    """

    @property
    def applicable_job_titles(self) -> list[str] | None: ...

    @property
    def required_certifications(self) -> list[str] | None: ...

    @property
    def certification_match_type(self) -> str: ...


class RuleEligibilityService:
    """
    Filters the potential rule set (retrieved from persistence) against complex
    employee-specific criteria (certifications, job title).
    """

    def __init__(
        self,
        certification_service: ICertificationService,
        rule_retriever_service: IRuleRetrievalService,
    ):
        self.certification_service = certification_service
        self.rule_retrieval_service = rule_retriever_service

    def get_applicable_rules(
        self,
        employee: Employee,
        shift: Shift,
    ) -> tuple[list[IDifferentialRule], list[IOvertimeRule]]:
        """
        Retrieves all rules applicable to the employee and performs the final
        in-memory filtering (certifications, job title).

        Returns: (List of applicable Differential Rules, List of applicable Overtime Rules)
        """

        # Differential rules (Used for eligibility and slicing)
        potential_diff_rules = (
            self.rule_retrieval_service.get_differential_rules_by_context(
                employee, shift
            )
        )

        # Overtime rules (Used for threshold calculation)
        potential_ot_rules = self.rule_retrieval_service.get_overtime_rules_by_context(
            employee, shift
        )

        # Filter Differential Rules (requires job title/cert checks)
        filtered_diff_rules = [
            rule
            for rule in potential_diff_rules
            if self._is_applicable_to_employee(rule, employee, shift)
        ]

        # Filter Overtime Rules (requires job title/cert checks)
        # Note: We must ensure the filtering logic works for both types of rules.
        filtered_ot_rules = [
            rule
            for rule in potential_ot_rules
            if self._is_applicable_to_employee(rule, employee, shift)
        ]

        # FIX: Priority sorting should happen here, as the DB might not have sorted them correctly
        filtered_diff_rules.sort(key=lambda r: r.priority, reverse=True)
        filtered_ot_rules.sort(key=lambda r: r.priority, reverse=True)

        return filtered_diff_rules, filtered_ot_rules

    def _is_applicable_to_employee(
        self,
        rule: RuleEligibilityCriteria,
        employee: Employee,
        shift: Shift,
    ) -> bool:
        """
        Logic for checking employee attributes (seniority, union, certifications)
        against the rule's criteria.
        """

        if rule.applicable_job_titles:
            if employee.job_title not in rule.applicable_job_titles:
                return False

        # 2. Check Certifications
        if rule.required_certifications:
            if not self._check_certification_eligibility(
                employee.employee_id,
                rule.required_certifications,
                rule.certification_match_type,
                shift.shift_start_dt,
            ):
                return False

        return True  # All criteria passed

    def _check_certification_eligibility(
        self,
        employee_id: str,
        required_certs: list[str],
        match_type: str,
        check_date: whenever.ZonedDateTime,
    ) -> bool:
        """Helper function to perform the actual lookup and validation."""

        # 1. Get the status of all required certifications for the employee at the shift start time
        cert_statuses = [
            self.certification_service.is_certification_active(
                employee_id,
                cert_name,
                check_date,
            )
            for cert_name in required_certs
        ]

        # 2. Apply the matching logic
        if match_type == "ALL":
            # Must be eligible for all required certifications (AND logic)
            return all(cert_statuses)

        if match_type == "ANY":
            # Must be eligible for at least one of the required certifications (OR logic)
            return any(cert_statuses)

        else:
            raise ValueError(f"Unknown certification match type: {match_type}")
