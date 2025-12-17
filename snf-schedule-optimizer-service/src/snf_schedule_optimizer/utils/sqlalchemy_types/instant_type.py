from datetime import UTC, datetime

import whenever
from sqlalchemy import DateTime, Dialect, TypeDecorator


class InstantType(TypeDecorator[whenever.Instant]):
    """
    SQLAlchemy type for storing whenever.Instant as a UTC timestamp.
    """

    impl = DateTime(timezone=True)  # Underlying SQL type is TIMESTAMPTZ
    cache_ok = True  # Safe to cache in SQLAlchemy 2.0+

    def process_bind_param(
        self, value: whenever.Instant | None, dialect: Dialect
    ) -> datetime | None:
        """Convert Instant to standard Python datetime for storage."""
        if value is None:
            return None

        # whenever.Instant.py_datetime() returns a standard, aware python datetime
        return value.py_datetime()

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> whenever.Instant | None:
        """Convert standard Python datetime from DB back to Instant."""
        if value is None:
            return None

        # Handling for drivers that return naive datetimes (like SQLite or some MySQL configs)
        # We assume if it's in the DB, it was stored as UTC.
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)

        return whenever.Instant.from_py_datetime(value)
