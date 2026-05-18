"""Idempotency key repository for deduplicating mutations."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.sqlalchemy_models.idempotency_key import (
    IdempotencyKeyModel,
)


class IdempotencyStore:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, key: str) -> bytes | None:
        result = await self._session.execute(
            select(IdempotencyKeyModel.response_payload).where(
                IdempotencyKeyModel.key == key
            )
        )
        return result.scalar_one_or_none()

    async def set(self, key: str, response_payload: bytes) -> None:
        model = IdempotencyKeyModel(key=key, response_payload=response_payload)
        self._session.add(model)
        await self._session.flush()
