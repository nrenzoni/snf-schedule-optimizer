import asyncio
from dataclasses import replace

import whenever

from snf_schedule_optimizer.domain.payroll.interfaces import (
    IEmployeeRulesRepo,
    IFacilityRulesRepo,
    IFacilityRulesService,
)
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    EmployeeTimeSettings,
    MealDeductionRules,
    PunchType,
    RoundingType,
    SplitDayType,
)


class FacilityRulesService(IFacilityRulesService):
    """
    DOMAIN SERVICE: Orchestrates the resolution of payroll and timekeeping rules.
    It resolves the hierarchy of rules (System -> Facility -> Employee) to create
    immutable configuration objects for time reconciliation.
    """

    def __init__(
        self,
        facility_rule_retriever: IFacilityRulesRepo,
        employee_rule_retriever: IEmployeeRulesRepo,
    ):
        self.facility_rule_retriever = facility_rule_retriever
        self.employee_rule_retriever = employee_rule_retriever

    async def apply_rounding(
        self,
        raw_time: whenever.ZonedDateTime,
        punch_type: PunchType,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
    ) -> whenever.ZonedDateTime:
        """
        Business logic: Rounds time based on the facility's specific unit.
        """
        config = await self.facility_rule_retriever.get_active_config(
            org_id,
            facility_id,
            raw_time,
        )

        # Default to 6-minute rounding if no config exists
        unit = config.rounding_unit_minutes if config else 6

        # Rounding logic implementation
        # (Assuming a domain utility exists for the math)
        minutes = raw_time.minute
        rounded_minutes = (round(minutes / unit) * unit) % 60

        if rounded_minutes == 0 and minutes > 30:
            return raw_time.add(hours=1).replace(minute=0, second=0)
        return raw_time.replace(minute=rounded_minutes, second=0)

    async def get_time_settings(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        check_dt: whenever.ZonedDateTime,
    ) -> EmployeeTimeSettings:
        """
        Calculates the effective timekeeping settings for an employee.
        Orchestrates parallel retrieval and applies override precedence.
        """
        # 1. Fetch data in parallel to avoid sequential blocking
        fac_task = self.facility_rule_retriever.get_active_config(
            org_id,
            facility_id,
            check_dt,
        )
        emp_task = self.employee_rule_retriever.get_employee_rule_overrides(
            org_id,
            employee_id,
            check_dt,
        )

        fac_config, emp_override = await asyncio.gather(fac_task, emp_task)

        # 2. Layer 1: System Defaults
        # Start with a hardcoded baseline representing global company policy.
        settings = EmployeeTimeSettings(
            pairing_threshold=whenever.DateTimeDelta(hours=14),
            split_day_threshold_time=whenever.Time(3, 0, 0),
            split_day_day_type=SplitDayType.CURRENT,
            shift_separator_time=whenever.Time(7, 0, 0),
            shift_grace_window=whenever.DateTimeDelta(minutes=15),
            rounding_unit_minutes=6,
            rounding_type=RoundingType.NEAREST,
            shift_seperator_enabled=True,
        )

        # Layer 2: Facility Overrides
        if fac_config:
            settings = replace(
                settings,
                rounding_unit_minutes=fac_config.rounding_unit_minutes,
                # Map other specific fields from the facility DB model DTO
                # shift_separator_time=fac_config.shift_separator_time,
            )

        # Layer 3: Employee Overrides (Highest Precedence)
        if emp_override:
            # We explicitly check for None to allow partial overrides
            if emp_override.rounding_unit_minutes is not None:
                settings = replace(
                    settings, rounding_unit_minutes=emp_override.rounding_unit_minutes
                )

        # Example of boolean toggle override
        # if emp_override.auto_meal_deduction_enabled is not None:
        #     settings = replace(settings, ...)

        # 5. Return Immutable Domain Object
        return settings

    async def get_meal_deduction_rules(
        self,
        org_id: DomainPrimaryKeyType,
        facility_id: DomainPrimaryKeyType,
        check_dt: whenever.ZonedDateTime,
    ) -> MealDeductionRules | None:
        """
        Extracts specific meal logic from the active facility configuration.
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
