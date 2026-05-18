"""Unit tests for tenant RLS context management."""

from snf_schedule_optimizer.persistence.tenant import (
    _current_org_id,
    get_current_org_id,
    set_current_org_id,
)


class TestTenantContext:
    def test_set_and_get_current_org_id(self) -> None:
        set_current_org_id(42)
        assert get_current_org_id() == 42

    def test_context_var_is_isolated_across_requests(self) -> None:
        set_current_org_id(100)
        assert get_current_org_id() == 100

        # Simulate context reset
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
