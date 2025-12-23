import whenever
from sqlalchemy import JSON, Float, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.models import OvertimeTriggerType
from snf_schedule_optimizer.models.persistence_dtos import OvertimeRuleData
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class OvertimeRuleModel(SQLABase):
    __tablename__ = "overtime_rule"

    org_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    description: Mapped[str] = mapped_column(String(100))
    multiplier: Mapped[float] = mapped_column(Float, default=1.5)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Trigger Configuration
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    daily_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    weekly_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    consecutive_day_threshold: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    consecutive_hours_threshold: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    work_period_start_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_period_start_time: Mapped[whenever.Time | None] = mapped_column(
        Time, nullable=True
    )
    daily_period_reset_time: Mapped[whenever.Time | None] = mapped_column(
        Time, nullable=True
    )
    days_of_week_trigger: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    applicable_job_titles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    required_certifications: Mapped[list[str] | None] = mapped_column(  # noqa: F821
        JSON, nullable=True
    )
    certification_match_type: Mapped[str] = mapped_column(String(10), default="ALL")
    contract_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def to_domain(self) -> OvertimeRuleData:
        return OvertimeRuleData(
            rule_id=self.rule_id,
            org_id=self.org_id,
            description=self.description,
            multiplier=self.multiplier,
            priority=self.priority,
            trigger_type=OvertimeTriggerType(self.trigger_type),
            daily_threshold=self.daily_threshold,
            weekly_threshold=self.weekly_threshold,
            consecutive_day_threshold=self.consecutive_day_threshold,
            consecutive_hours_threshold=self.consecutive_hours_threshold,
            work_period_start_day=whenever.Weekday(self.work_period_start_day)
            if self.work_period_start_day is not None
            else None,
            work_period_start_time=self.work_period_start_time,
            daily_period_reset_time=self.daily_period_reset_time,
            days_of_week_trigger=[
                whenever.Weekday(d) for d in self.days_of_week_trigger
            ]
            if self.days_of_week_trigger
            else None,
            applicable_job_titles=self.applicable_job_titles,
            required_certifications=self.required_certifications,
            certification_match_type=self.certification_match_type,
            contract_id=self.contract_id,
        )
