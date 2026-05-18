"""Simple in-process domain event bus for cross-context communication."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import uuid4

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""

    event_id: str = field(default_factory=lambda: str(uuid4()))


class EventBus:
    """In-memory publish/subscribe event bus."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type].append(handler)
        logger.debug("EventBus: subscribed handler to %s", event_type.__name__)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all registered handlers."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug("EventBus: no handlers for %s", event_type.__name__)
            return

        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("EventBus: handler failed for %s", event_type.__name__)

    def clear(self) -> None:
        """Remove all handlers (useful for testing)."""
        self._handlers.clear()


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _event_bus
