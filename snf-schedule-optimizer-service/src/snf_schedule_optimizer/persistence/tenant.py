"""PostgreSQL Row-Level Security context management.

Session auto-injection
----------------------
A SQLAlchemy ``do_orm_execute`` listener is registered at import time so
that every ORM query automatically runs ``SET LOCAL app.current_org_id``
*before* the first statement the session issues.  Handlers only need to
call :func:`set_current_org_id` after tenant validation — the session
picks it up transparently and no per-endpoint boilerplate is required.
"""

from contextvars import ContextVar
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.orm import Session

_current_org_id: ContextVar[int] = ContextVar("current_org_id")

_TENANT_SET_MARKER = "_snf_rls_tenant_set"


def get_current_org_id() -> int:
    return _current_org_id.get()


def set_current_org_id(org_id: int) -> None:
    _current_org_id.set(org_id)


# ---------------------------------------------------------------------------
# Session-level auto-injection
# ---------------------------------------------------------------------------


@event.listens_for(Session, "do_orm_execute")
def _inject_tenant_into_session(orm_execute_state: Any) -> None:
    """Ensure ``SET LOCAL app.current_org_id`` runs once per session."""
    session: Session = orm_execute_state.session

    if _TENANT_SET_MARKER in session.info:
        return

    session.info[_TENANT_SET_MARKER] = True

    try:
        org_id = get_current_org_id()
    except LookupError:
        return

    session.connection().execute(
        text(f"SET LOCAL app.current_org_id = {org_id}"),
    )
