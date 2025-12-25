import whenever
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.domain.payroll.interfaces import IEmployeeRulesRepo
from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    EmployeeRuleOverride,
)
from snf_schedule_optimizer.sqlalchemy_models.employee_rule_override import (
    EmployeeRuleOverrideModel,
)


class SQLEmployeeRulesRepo(IEmployeeRulesRepo):
    """
    ADAPTER: Handles SQL specifics for employee-level overrides.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_employee_rule_overrides(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        check_date: whenever.ZonedDateTime,
    ) -> EmployeeRuleOverride | None:
        """
        Fetches employee overrides with tenant scoping.
        """
        stmt = (
            select(EmployeeRuleOverrideModel)
            .where(
                and_(
                    EmployeeRuleOverrideModel.org_id == org_id,
                    EmployeeRuleOverrideModel.id == employee_id,
                    EmployeeRuleOverrideModel.effective_date <= check_date,
                )
            )
            .order_by(desc(EmployeeRuleOverrideModel.effective_date))
            .limit(1)
        )

        result = await self.db_session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return None

        return EmployeeRuleOverride(
            employee_id=record.id,
            rounding_unit_minutes=record.rounding_unit_minutes,
            auto_meal_deduction_enabled=record.auto_meal_deduction_enabled,
        )
