from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class OptimizationRunModel(SQLABase):
    __tablename__ = "optimization_run"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    facility_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    schedule_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    base_schedule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_schedule_id: Mapped[int | None] = mapped_column(Integer)
    result_schedule_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_message: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    error_details: Mapped[str | None] = mapped_column(String)
    client_request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    patches_json: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    persist_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    policy_start_date: Mapped[str | None] = mapped_column(String(10))
    policy_end_date: Mapped[str | None] = mapped_column(String(10))
    snapshot_id: Mapped[str | None] = mapped_column(String(64), index=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), index=True)
    claim_token: Mapped[str | None] = mapped_column(String(64), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    termination_reason: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    settings_json: Mapped[str | None] = mapped_column(String)
    summary_json: Mapped[str | None] = mapped_column(String)
    stats_json: Mapped[str | None] = mapped_column(String)
    financials_json: Mapped[str | None] = mapped_column(String)
