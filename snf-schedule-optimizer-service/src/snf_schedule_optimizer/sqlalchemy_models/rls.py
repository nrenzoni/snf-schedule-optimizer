"""Declarative Row-Level Security DDL helpers.

Uses SQLAlchemy DDL events so that RLS policies are attached to model
table metadata and applied automatically on ``create_all()``.
"""

import warnings

from sqlalchemy import DDL, event


def enable_tenant_isolation(table_obj: object) -> None:
    """Attach RLS DDL listeners to a SQLAlchemy table.

    Registers ``after_create`` listeners that emit:

    * ``ALTER TABLE {name} ENABLE ROW LEVEL SECURITY``
    * ``ALTER TABLE {name} FORCE ROW LEVEL SECURITY``
    * ``CREATE POLICY tenant_isolation`` that filters every row by
      ``org_id`` using the session-level GUC
      ``app.current_org_id``.
    """
    if not hasattr(table_obj, "name"):
        warnings.warn(
            f"enable_tenant_isolation received {type(table_obj)} which "
            f"has no .name attribute — skipping RLS registration.",
            stacklevel=2,
        )
        return

    t_name: str = table_obj.name

    enable_rls = DDL(f"ALTER TABLE {t_name} ENABLE ROW LEVEL SECURITY;")  # type: ignore[no-untyped-call]
    force_rls = DDL(f"ALTER TABLE {t_name} FORCE ROW LEVEL SECURITY;")  # type: ignore[no-untyped-call]
    create_policy = DDL(  # type: ignore[no-untyped-call]
        f"CREATE POLICY tenant_isolation ON {t_name} "
        "USING (org_id = current_setting('app.current_org_id', true)::integer) "
        "WITH CHECK (org_id = current_setting('app.current_org_id', true)::integer);"
    )

    event.listen(table_obj, "after_create", enable_rls)
    event.listen(table_obj, "after_create", force_rls)
    event.listen(table_obj, "after_create", create_policy)
