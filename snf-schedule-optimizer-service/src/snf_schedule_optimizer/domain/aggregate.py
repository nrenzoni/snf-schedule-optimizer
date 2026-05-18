"""Aggregate root marker protocol for domain-driven design boundaries."""
from typing import Protocol


class AggregateRoot(Protocol):
    """Marker protocol for aggregate roots."""

    @property
    def version(self) -> int: ...
