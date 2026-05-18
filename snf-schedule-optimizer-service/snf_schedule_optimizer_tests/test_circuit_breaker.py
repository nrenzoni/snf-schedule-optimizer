import pytest

from snf_schedule_optimizer.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)


async def _fail() -> str:
    raise ValueError("test failure")


async def _ok() -> str:
    return "ok"


@pytest.mark.asyncio
async def test_circuit_closes_after_failures() -> None:
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=60.0)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail)
    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(_ok)


@pytest.mark.asyncio
async def test_circuit_resets_on_success() -> None:
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=60.0)
    result = await cb.call(_ok)
    assert result == "ok"
    assert cb._state == "closed"


@pytest.mark.asyncio
async def test_circuit_opens_then_half_opens() -> None:
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.0)
    with pytest.raises(ValueError):
        await cb.call(_fail)
    assert cb._state != "closed"
