from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class OptimizationSnapshotModel(SQLABase):
    __tablename__ = "optimization_snapshot"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    org_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    schedule_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    base_schedule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    decision_end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    policy_start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    policy_end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    payload_json: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
