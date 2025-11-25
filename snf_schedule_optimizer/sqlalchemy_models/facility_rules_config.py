import datetime

from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy import Date, Integer, Float, Boolean, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class FacilityRulesConfigModel(SQLABase):
    """
    SQLAlchemy ORM model for storing facility-specific time and payroll rules.
    """
    __tablename__ = 'facility_rules_config'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey('facility.id'), index=True, nullable=False)

    # Rounding Rule
    rounding_unit_minutes: Mapped[int] = mapped_column(Integer, default=6)  # e.g., 6 (for 1/10th hour)

    # Meal Deduction Rules (Stored as normalized fields or a dedicated JSON/HSTORE type for flexibility)
    meal_deduction_threshold_hours: Mapped[float] = mapped_column(Float, default=6.0)
    meal_deduction_duration_hours: Mapped[float] = mapped_column(Float, default=0.5)  # 30 mins
    meal_is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)

    # Optional: Rule validity dates if rules change frequently
    effective_date: Mapped[datetime.date] = mapped_column(Date)

    # Note: In a complex system, deduction rules would be in a separate 1:N table.
