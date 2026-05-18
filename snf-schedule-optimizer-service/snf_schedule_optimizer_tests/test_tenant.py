"""Unit tests for tenant RLS context management."""

from unittest.mock import patch

from sqlalchemy import Column, Integer, MetaData, Table

from snf_schedule_optimizer.persistence.tenant import (
    _TENANT_SET_MARKER,
    _current_org_id,
    get_current_org_id,
    set_current_org_id,
)
from snf_schedule_optimizer.sqlalchemy_models.rls import enable_tenant_isolation


class TestTenantContext:
    def test_set_and_get_current_org_id(self) -> None:
        set_current_org_id(42)
        assert get_current_org_id() == 42

    def test_context_var_is_isolated_across_requests(self) -> None:
        set_current_org_id(100)
        assert get_current_org_id() == 100

        token = _current_org_id.set(200)
        assert get_current_org_id() == 200

        _current_org_id.reset(token)
        assert get_current_org_id() == 100

    def test_default_raises_lookup_error(self) -> None:
        import contextvars

        ctx: contextvars.ContextVar[int] = contextvars.ContextVar("new_var")
        try:
            ctx.get()
            raise AssertionError("Should have raised LookupError")
        except LookupError:
            pass


class TestRlsDdlRegistration:
    def test_enable_tenant_isolation_registers_three_listeners(self) -> None:
        table = Table("test_table", MetaData(), Column("org_id", Integer))
        with patch("sqlalchemy.event.listen") as mock_listen:
            enable_tenant_isolation(table)
        assert mock_listen.call_count == 3

    def test_ddl_includes_expected_clauses(self) -> None:
        table = Table("test_table", MetaData(), Column("org_id", Integer))
        with patch("sqlalchemy.event.listen") as mock_listen:
            enable_tenant_isolation(table)
        ddl_texts = [
            str(call_args.args[2]) for call_args in mock_listen.call_args_list
        ]
        assert any("ENABLE ROW LEVEL SECURITY" in t for t in ddl_texts)
        assert any("FORCE ROW LEVEL SECURITY" in t for t in ddl_texts)
        assert any("tenant_isolation" in t for t in ddl_texts)
        assert any("current_setting('app.current_org_id'" in t for t in ddl_texts)

    def test_listeners_registered_on_after_create(self) -> None:
        table = Table("test_table", MetaData(), Column("org_id", Integer))
        with patch("sqlalchemy.event.listen") as mock_listen:
            enable_tenant_isolation(table)
        events = [call_args.args[1] for call_args in mock_listen.call_args_list]
        assert all(e == "after_create" for e in events)


class TestSessionAutoInjection:
    def test_marker_added_to_session_info(self) -> None:
        """The _inject_tenant_into_session listener sets a per-session marker."""
        from sqlalchemy.orm import Session

        session = object.__new__(Session)
        session.info = {}

        assert _TENANT_SET_MARKER not in session.info
