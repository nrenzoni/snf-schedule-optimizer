"""PostgreSQL Row-Level Security context management."""
from contextvars import ContextVar

_current_org_id: ContextVar[int] = ContextVar("current_org_id")

def get_current_org_id() -> int:
    return _current_org_id.get()

def set_current_org_id(org_id: int) -> None:
    _current_org_id.set(org_id)
