import whenever
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import and_

from snf_schedule_optimizer.models import FacilityRulesConfig
from snf_schedule_optimizer.services.payroll.interfaces import IFacilityRulesRetriever
from snf_schedule_optimizer.sqlalchemy_models.facility_rules_config import (
    FacilityRulesConfigModel,
)


class SQLFacilityRulesRetriever(IFacilityRulesRetriever):
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_active_config(
        self,
        org_id: str,
        facility_id: str,
        check_date: whenever.ZonedDateTime,
    ) -> FacilityRulesConfig | None:
        stmt = (
            select(FacilityRulesConfigModel)
            .where(
                and_(
                    FacilityRulesConfigModel.org_id == org_id,
                    FacilityRulesConfigModel.facility_id == facility_id,
                )
            )
            .order_by(desc(FacilityRulesConfigModel.effective_date))
            .limit(1)
        )

        record = (await self.db_session.execute(stmt)).scalar_one_or_none()

        if not record:
            return None

        return FacilityRulesConfig(
            rounding_unit_minutes=int(record.rounding_unit_minutes),
            meal_deduction_threshold_hours=float(record.meal_deduction_threshold_hours),
            meal_deduction_duration_hours=float(record.meal_deduction_duration_hours),
            meal_is_mandatory=bool(record.meal_is_mandatory),
        )
