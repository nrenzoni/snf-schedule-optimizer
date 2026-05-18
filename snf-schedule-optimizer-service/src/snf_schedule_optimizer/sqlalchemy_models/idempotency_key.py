from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from snf_schedule_optimizer.sqlalchemy_models.base import SQLABase


class IdempotencyKeyModel(SQLABase):
    __tablename__ = "idempotency_key"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    response_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
