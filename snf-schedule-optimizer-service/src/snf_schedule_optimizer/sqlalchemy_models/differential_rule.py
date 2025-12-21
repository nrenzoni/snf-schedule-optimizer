from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.models.data import DifferentialRuleData
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class DifferentialRuleModel(SQLABase):
    __tablename__ = "differential_rule"

    org_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), primary_key=True)

    description: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Store list of job titles as JSON or comma-separated string
    applicable_job_titles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    contract_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def to_data(self) -> DifferentialRuleData:
        return DifferentialRuleData(
            rule_id=self.rule_id,
            org_id=self.org_id,
            description=self.description,
            amount=self.amount,
            priority=self.priority,
            applicable_job_titles=self.applicable_job_titles,
            contract_id=self.contract_id,
        )
