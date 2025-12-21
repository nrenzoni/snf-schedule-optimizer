import whenever

from snf_schedule_optimizer.models import EmployeeTimeSettings, MealDeductionRules
from snf_schedule_optimizer.services.payroll.interfaces import (
    IEmployeeRulesRetriever,
    IFacilityRulesRetriever,
    IFacilityRulesService,
)


class FacilityRulesService(IFacilityRulesService):
    """
    DOMAIN SERVICE: Contains pure business logic.
    Uses a Retriever to get the raw config, but constructs the Domain Objects.
    """

    def __init__(
        self,
        facility_rule_retriever: IFacilityRulesRetriever,
        employee_rule_retriever: IEmployeeRulesRetriever,
    ):
        self.facility_rule_retriever = facility_rule_retriever
        self.employee_rule_retriever = employee_rule_retriever

    async def apply_rounding(
        self,
        org_id: str,
        raw_time: whenever.ZonedDateTime,
        facility_id: str,
    ) -> whenever.ZonedDateTime:
        """
        Business logic: Rounds time based on the facility's specific unit.
        """
        config = await self.facility_rule_retriever.get_active_config(
            org_id,
            facility_id,
            raw_time,
        )

        rounding_unit = config.rounding_unit_minutes if config else 6

        # In a real app, TimeRoundingUtility would be a domain helper
        # return TimeRoundingUtility.round_to_nearest_unit(raw_time, rounding_unit)
        return raw_time  # Placeholder for logic

    async def get_time_settings(
        self,
        org_id: str,
        employee_id: str,
        facility_id: str,
        check_dt: whenever.ZonedDateTime,
    ) -> EmployeeTimeSettings:
        """
        Combines facility-level defaults with employee-specific overrides
        to provide the Reconciler with a complete set of rules.
        """
        fac_config = self.facility_rule_retriever.get_active_config(
            org_id,
            facility_id,
            check_dt,
        )
        emp_overrides = await self.employee_rule_retriever.get_employee_rule_overrides(
            org_id,
            employee_id,
            check_dt,
        )

        # Merge logic: Employee overrides take precedence over Facility defaults
        settings_data = EmployeeTimeSettings(
            rounding_unit_minutes=6,
            auto_meal_deduction_enabled=True,
            grace_period_minutes=5,
        )

        if fac_config:
            settings_data.update(fac_config)
        if emp_overrides:
            settings_data.update(emp_overrides)

        # Map to Domain Object (EmployeeTimeSettings)
        # return EmployeeTimeSettings(**settings_data)
        return settings_data

    async def get_meal_deduction_rules(
        self,
        org_id: str,
        facility_id: str,
        check_dt: whenever.ZonedDateTime,
    ) -> MealDeductionRules | None:
        """
        Extracts specific meal logic from the active configuration.
        """
        config = await self.facility_rule_retriever.get_active_config(
            org_id,
            facility_id,
            check_dt,
        )
        if not config:
            return None

        return MealDeductionRules(
            meal_threshold_hours=config.meal_deduction_threshold_hours,
            meal_duration_hours=config.meal_deduction_duration_hours,
        )
