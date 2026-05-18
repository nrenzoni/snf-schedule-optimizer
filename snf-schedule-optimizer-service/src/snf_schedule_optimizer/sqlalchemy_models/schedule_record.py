from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class ScheduleRecordModel(SQLABase):
    __tablename__ = "schedule_record"

    schedule_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(index=True, nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(ScheduleRecordModel.__table__)
