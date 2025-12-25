import datetime

import whenever
from sqlalchemy import Date, DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class InstantType(TypeDecorator[whenever.Instant]):
    """
    SQLAlchemy type for storing whenever.Instant as a UTC timestamp.
    """

    impl = DateTime(timezone=True)  # Underlying SQL type is TIMESTAMPTZ
    cache_ok = True  # Safe to cache in SQLAlchemy 2.0+

    def process_bind_param(
        self, value: whenever.Instant | None, dialect: Dialect
    ) -> datetime.datetime | None:
        """Convert Instant to standard Python datetime for storage."""
        if value is None:
            return None

        # whenever.Instant.py_datetime() returns a standard, aware python datetime
        return value.py_datetime()

    def process_result_value(
        self, value: datetime.datetime | None, dialect: Dialect
    ) -> whenever.Instant | None:
        """Convert standard Python datetime from DB back to Instant."""
        if value is None:
            return None

        # Handling for drivers that return naive datetimes (like SQLite or some MySQL configs)
        # We assume if it's in the DB, it was stored as UTC.
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.UTC)

        return whenever.Instant.from_py_datetime(value)


class DateType(TypeDecorator[whenever.Date]):
    """
    Handles seamless conversion between PostgreSQL 'DATE'
    and Python 'whenever.Date'.
    """

    impl = Date
    cache_ok = True

    def process_bind_param(
        self, value: whenever.Date | None, dialect: Dialect
    ) -> datetime.date | None:
        """Convert whenever.Date -> Python datetime.date for the DB driver."""
        if value is None:
            return None
        return value.py_date()

    def process_result_value(
        self, value: datetime.date | None, dialect: Dialect
    ) -> whenever.Date | None:
        """Convert Python datetime.date -> whenever.Date for the application."""
        if value is None:
            return None
        return whenever.Date.from_py_date(value)
