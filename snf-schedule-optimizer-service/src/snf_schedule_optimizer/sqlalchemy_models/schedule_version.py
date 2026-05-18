from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class ScheduleVersionModel(SQLABase):
    __tablename__ = "schedule_version"

    schedule_version_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    schedule_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    org_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


from snf_schedule_optimizer.sqlalchemy_models.rls import (
    enable_tenant_isolation,
)

enable_tenant_isolation(ScheduleVersionModel.__table__)
