import whenever
from sqlalchemy import JSON, Float, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.models import DifferentialRuleType, DifferentialType
from snf_schedule_optimizer.models.persistence_dtos import DifferentialRuleData
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class DifferentialRuleModel(SQLABase):
    __tablename__ = "differential_rule"

    org_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    description: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    differential_type: Mapped[str] = mapped_column(String(20), nullable=False)
    multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    flat: Mapped[float | None] = mapped_column(Float, nullable=True)

    start_time: Mapped[whenever.Time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[whenever.Time | None] = mapped_column(Time, nullable=True)

    applicable_job_titles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    contract_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def to_domain(self) -> DifferentialRuleData:
        return DifferentialRuleData(
            rule_id=self.rule_id,
            org_id=self.org_id,
            description=self.description,
            priority=self.priority,
            rule_type=DifferentialRuleType(self.rule_type),
            differential_type=DifferentialType(self.differential_type),
            multiplier=self.multiplier,
            flat=self.flat,
            start_time=self.start_time,
            end_time=self.end_time,
            applicable_job_titles=self.applicable_job_titles,
            contract_id=self.contract_id,
        )
