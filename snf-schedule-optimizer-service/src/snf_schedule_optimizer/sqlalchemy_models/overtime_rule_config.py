import datetime as dt
from typing import List, Optional

from sqlalchemy import Integer, String, Float, Boolean, Date, Time
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pendulum import WeekDay

from .base import SQLABase


class OvertimeRuleConfig(SQLABase):
    """
    SQLAlchemy ORM model representing a single overtime rule configuration
    stored in the PostgreSQL database.
    """
    __tablename__ = 'overtime_rules_config'

    # --- Primary Key and Metadata ---
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Description is implicitly nullable
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_date: Mapped[Date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)

    # Priority for tie-breaking: Higher number means checked first
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # --- IOvertimeRule Fields ---
    multiplier: Mapped[float] = mapped_column(Float, nullable=False)  # e.g., 1.5, 2.0

    # Applicable Employee/Unit Criteria (used for SQL filtering)
    # Stored as a list of strings (PostgreSQL ARRAY type)
    applicable_job_titles: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    union_contract_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g., 'Local_123'

    # --- OvertimeTrigger Fields (Thresholds) ---
    daily_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # e.g., 8.0
    weekly_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # e.g., 40.0

    # Consecutive Thresholds
    consecutive_day_threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    consecutive_hours_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- OvertimeTrigger Fields (Period Definitions) ---

    # Weekly Period Start: Stored as integer (pendulum.WeekDay value)
    work_period_start_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Weekly Period Start Time: Stored as separate hour/minute/second fields
    # OR you can use SQLAlchemy's built-in Time type for simpler mapping
    work_period_start_time: Mapped[Optional[dt.time]] = mapped_column(Time, nullable=True)

    # Daily Period Reset Time (for non-midnight day resets)
    daily_period_reset_time: Mapped[Optional[dt.time]] = mapped_column(Time, nullable=True)

    # Specific Days of Week Trigger: Stored as array of integers (WeekDay values)
    days_of_week_trigger: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer), nullable=True)

    def __repr__(self) -> str:
        return f"<OvertimeRuleConfig(name='{self.name}', multiplier={self.multiplier})>"
