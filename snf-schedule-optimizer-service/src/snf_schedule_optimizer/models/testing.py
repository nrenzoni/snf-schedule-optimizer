import dataclasses

import pendulum


@dataclasses.dataclass(frozen=True)
class MockCertificationRecord:
    """Internal structure to store certification status for testing."""

    certification_name: str
    expiration_date: pendulum.Date | None
    # acquired_date is omitted for simplicity but would be used in a full implementation
