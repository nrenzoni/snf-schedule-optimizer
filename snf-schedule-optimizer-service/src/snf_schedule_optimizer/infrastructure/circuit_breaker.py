"""Circuit breaker pattern for external service calls."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

T = TypeVar("T")

CircuitState = Literal["closed", "open", "half_open"]


class CircuitBreakerOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state: CircuitState = "closed"
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: object,
        **kwargs: object,
    ) -> T:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                self._state = "half_open"
            else:
                raise CircuitBreakerOpenError("Circuit is open")

        try:
            result = await fn(*args, **kwargs)
            if self._state == "half_open":
                self._state = "closed"
                self._failure_count = 0
            return result
        except Exception:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if (
                self._state == "half_open"
                or self._failure_count >= self.failure_threshold
            ):
                self._state = "open"
            raise

    def call_sync(
        self,
        fn: Callable[..., T],
        *args: object,
        **kwargs: object,
    ) -> T:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                self._state = "half_open"
            else:
                raise CircuitBreakerOpenError("Circuit is open")

        try:
            result = fn(*args, **kwargs)
            if self._state == "half_open":
                self._state = "closed"
                self._failure_count = 0
            return result
        except Exception:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if (
                self._state == "half_open"
                or self._failure_count >= self.failure_threshold
            ):
                self._state = "open"
            raise
