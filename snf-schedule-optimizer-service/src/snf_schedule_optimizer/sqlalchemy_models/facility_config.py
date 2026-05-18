import datetime

import whenever
from sqlalchemy import Float, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.models import FacilityConfig
from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class FacilityConfigModel(SQLABase):
    """
    SQLAlchemy model representing the 'facility_config' table.
    Stores the static rules and metadata for each building.
    """

    __tablename__ = "facility_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)

    # Core Scheduling Parameters
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., 'America/New_York'
    shifts_per_day: Mapped[int] = mapped_column(Integer, default=3)
    overtime_threshold_hours_per_week: Mapped[int] = mapped_column(Integer, default=40)

    # Work Period Boundaries
    # Stored as integer (0-6) mapping to whenever.Weekday
    start_of_work_week_day: Mapped[int] = mapped_column(Integer, default=0)
    start_of_work_day_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)

    # Pay Period Definition
    pay_period_weeks: Mapped[int] = mapped_column(Integer, default=1)

    # Pay Multipliers
    weekend_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    night_shift_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    # Workforce policy defaults used by the optimizer.
    default_hprd_rn: Mapped[float] = mapped_column(Float, default=0.5)
    default_hprd_lpn: Mapped[float] = mapped_column(Float, default=0.0)
    default_hprd_cna: Mapped[float] = mapped_column(Float, default=2.4)
    default_hprd_total: Mapped[float] = mapped_column(Float, default=3.5)
    min_rest_hours_between_shifts: Mapped[float] = mapped_column(Float, default=10.0)
    max_consecutive_work_days: Mapped[int] = mapped_column(Integer, default=5)
    max_total_hours_per_pay_period: Mapped[float] = mapped_column(Float, default=80.0)

    def to_domain(self) -> FacilityConfig:
        """
        Maps the database record to the domain FacilityConfig object.
        """
        return FacilityConfig(
            org_id=self.org_id,
            facility_id=self.facility_id,
            shifts_per_day=int(self.shifts_per_day),
            overtime_threshold_hours_per_week=int(
                self.overtime_threshold_hours_per_week
            ),
            # Convert integer weekday to whenever.Weekday
            start_of_work_week_day=whenever.Weekday(self.start_of_work_week_day),
            # Convert py-time to whenever.Time
            start_of_work_day_time=whenever.Time(
                self.start_of_work_day_time.hour,
                self.start_of_work_day_time.minute,
                self.start_of_work_day_time.second,
            ),
            pay_period=whenever.DateDelta(weeks=self.pay_period_weeks),
            weekend_multiplier=float(self.weekend_multiplier),
            night_shift_multiplier=float(self.night_shift_multiplier),
            # Note: timezone is used by retrievers to hydrate ZonedDateTime
            tz=self.timezone,
            default_hprd_rn=float(self.default_hprd_rn),
            default_hprd_lpn=float(self.default_hprd_lpn),
            default_hprd_cna=float(self.default_hprd_cna),
            default_hprd_total=float(self.default_hprd_total),
            min_rest_hours_between_shifts=float(self.min_rest_hours_between_shifts),
            max_consecutive_work_days=int(self.max_consecutive_work_days),
            max_total_hours_per_pay_period=float(self.max_total_hours_per_pay_period),
        )

    @staticmethod
    def from_domain(domain: FacilityConfig) -> "FacilityConfigModel":
        """
        Creates a FacilityConfigModel from a domain FacilityConfig object.
        """
        return FacilityConfigModel(
            org_id=domain.org_id,
            facility_id=domain.facility_id,
            shifts_per_day=domain.shifts_per_day,
            overtime_threshold_hours_per_week=domain.overtime_threshold_hours_per_week,
            start_of_work_week_day=domain.start_of_work_week_day.value,
            start_of_work_day_time=datetime.time(
                domain.start_of_work_day_time.hour,
                domain.start_of_work_day_time.minute,
                domain.start_of_work_day_time.second,
            ),
            pay_period_weeks=domain.pay_period.in_months_days()[1] // 7,
            weekend_multiplier=domain.weekend_multiplier,
            night_shift_multiplier=domain.night_shift_multiplier,
            timezone=domain.tz,
            default_hprd_rn=domain.default_hprd_rn,
            default_hprd_lpn=domain.default_hprd_lpn,
            default_hprd_cna=domain.default_hprd_cna,
            default_hprd_total=domain.default_hprd_total,
            min_rest_hours_between_shifts=domain.min_rest_hours_between_shifts,
            max_consecutive_work_days=domain.max_consecutive_work_days,
            max_total_hours_per_pay_period=domain.max_total_hours_per_pay_period,
        )


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(FacilityConfigModel.__table__)
