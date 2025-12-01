import pendulum
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from snf_schedule_optimizer.models.testing import MockCertificationRecord
from snf_schedule_optimizer.services.hr.interfaces import ICertificationService
from snf_schedule_optimizer.sqlalchemy_models.employee_certification import (
    EmployeeCertificationModel,
)


class CertificationServiceStaticListImpl(ICertificationService):
    """
    Concrete implementation of the certification service using a static,
    in-memory dictionary for testing validity and expiration.
    """

    def __init__(self, records: list[tuple[str, MockCertificationRecord]]):
        """
        Initializes the service with a list of (employee_id, record) tuples.

        Example: [
            ('EMP_A', MockCertificationRecord(name='ACLS', expiration_date=datetime.date(2026, 1, 1))),
            ('EMP_A', MockCertificationRecord(name='BLS', expiration_date=datetime.date(2024, 1, 1))), # EXPIRED
        ]
        """
        # Dictionary mapping employee_id -> List[MockCertificationRecord]
        self.employee_certs: dict[str, list[MockCertificationRecord]] = {}

        for employee_id, record in records:
            if employee_id not in self.employee_certs:
                self.employee_certs[employee_id] = []
            self.employee_certs[employee_id].append(record)

    def is_certification_active(
        self,
        employee_id: str,
        certification_name: str,
        check_date: pendulum.DateTime,
    ) -> bool:
        """
        Checks if the named certification is valid/unexpired for the employee
        on the specific check_date by querying the in-memory list.
        """

        if employee_id not in self.employee_certs:
            return False

        # Normalize check_date to a Python date object for comparison
        check_date_date = check_date.date()

        for record in self.employee_certs[employee_id]:
            if record.certification_name == certification_name:
                # Check 1: Expiration Date must be greater than or equal to the check date.
                # If cert expires on 2025-12-31, it is still valid FOR 2025-12-31.
                if (
                    record.expiration_date is None
                    or record.expiration_date >= check_date_date
                ):
                    return True

        return False


class SQLACertificationService(ICertificationService):
    """
    Concrete implementation using SQLAlchemy to query the Postgres employee_certification table.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def is_certification_active(
        self,
        employee_id: str,
        certification_name: str,
        check_date: pendulum.DateTime,
    ) -> bool:
        """
        Checks if the employee holds an unexpired certification on the required date.
        """

        # We must normalize the check_date to a standard Python date object
        # or compare it correctly within the SQL query, as expiration_date is typically a DATE type.
        check_date_for_db = check_date.date()

        # Construct the SQL query using SQLAlchemy's Core/ORM Select
        stmt = select(EmployeeCertificationModel).where(
            and_(
                EmployeeCertificationModel.employee_id == employee_id,
                EmployeeCertificationModel.certification_name == certification_name,
                # Crucial Check 1: The expiration date must be GREATER than or equal to the check date.
                # If the cert expires *before* the shift starts, it's invalid.
                EmployeeCertificationModel.expiration_date >= check_date_for_db,
                # Optional Check 2: The acquired date must be LESS than or equal to the check date
                # (Assuming the model has an 'acquired_date' field, though not explicitly in the placeholder)
                # EmployeeCertificationModel.acquired_date <= check_date_for_db
            )
        )

        # Execute the query
        result = self.db_session.execute(stmt).scalar_one_or_none()

        # If a record is found, it means the certification exists and is valid
        # (unexpired) on the specified check_date.
        return result is not None
