from typing import List

import pendulum

from snf_schedule_optimizer.models import Employee, Shift
from snf_schedule_optimizer.services.calculations.overtime_calculation import ThresholdOvertimeRule
from snf_schedule_optimizer.services.interfaces import ICertificationService, IDifferentialRule


class RuleEligibilityService:
    """Filters the master list of rules based on employee and shift context."""

    def __init__(
            self,
            certification_service: ICertificationService,
            all_rules: List[IDifferentialRule],
    ):
        self.certification_service = certification_service
        self.all_rules = all_rules

    def get_applicable_rules(
            self,
            employee: Employee,
            shift: Shift,
    ) -> List[IDifferentialRule]:
        """
        Returns only the rules the specific employee is eligible for on this shift.
        """

        # todo: filter by shift type/unit
        filtered_to_employee = [
            rule for rule in self.all_rules
            if self._is_applicable_to_employee(rule, employee, shift)
        ]

        # Add priority sorting here if needed

        return filtered_to_employee

    def _is_applicable_to_employee(
            self,
            rule: IDifferentialRule,
            employee: Employee,
            shift: Shift,
    ) -> bool:
        """
        Logic for checking employee attributes (seniority, union, certifications)
        against the rule's criteria.
        """

        if rule.applicable_job_titles and employee.job_title not in rule.applicable_job_titles:
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
            required_certs: List[str],
            match_type: str,
            check_date: pendulum.DateTime,
    ) -> bool:
        """Helper function to perform the actual lookup and validation."""

        # 1. Get the status of all required certifications for the employee at the shift start time
        cert_statuses = [
            self.certification_service.is_certification_active(
                employee_id,
                cert_name,
                check_date
            ) for cert_name in required_certs
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
