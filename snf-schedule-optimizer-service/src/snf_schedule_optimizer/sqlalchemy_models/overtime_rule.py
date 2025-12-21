from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.models.data import OvertimeRuleData
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class OvertimeRuleModel(SQLABase):
    __tablename__ = "overtime_rule"

    org_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), primary_key=True)

    multiplier: Mapped[float] = mapped_column(Float, default=1.5)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    applicable_job_titles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    contract_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def to_data(self) -> OvertimeRuleData:
        return OvertimeRuleData(
            rule_id=self.rule_id,
            org_id=self.org_id,
            multiplier=self.multiplier,
            priority=self.priority,
            applicable_job_titles=self.applicable_job_titles,
            contract_id=self.contract_id,
        )
