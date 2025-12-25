import whenever
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    FacilityConfig,
)
from snf_schedule_optimizer.models.persistence_dtos import EmployeeCertificationData
from snf_schedule_optimizer.models.testing import MockCertificationRecord
from snf_schedule_optimizer.services.hr.interfaces import (
    ICertificationRepo,
    ICertificationService,
)
from snf_schedule_optimizer.sqlalchemy_models.employee_certification import (
    EmployeeCertificationModel,
)


class CertificationServiceStaticListImpl(ICertificationService):
    """
    Concrete implementation of the certification service using a static,
    in-memory dictionary for testing validity and expiration.
    """

    def __init__(
        self,
        records: list[tuple[DomainPrimaryKeyType, MockCertificationRecord]],
        facility_config: FacilityConfig,
    ) -> None:
        """
        Initializes the service with a list of (employee_id, record) tuples.

        Example: [
            ('EMP_A', MockCertificationRecord(name='ACLS', expiration_date=datetime.date(2026, 1, 1))),
            ('EMP_A', MockCertificationRecord(name='BLS', expiration_date=datetime.date(2024, 1, 1))), # EXPIRED
        ]
        """
        # Dictionary mapping employee_id -> List[MockCertificationRecord]
        self.employee_certs: dict[
            DomainPrimaryKeyType, list[MockCertificationRecord]
        ] = {}

        for employee_id, record in records:
            if employee_id not in self.employee_certs:
                self.employee_certs[employee_id] = []
            self.employee_certs[employee_id].append(record)

        self.facility_config = facility_config

    async def is_certification_active(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        certification_name: str,
        check_date: whenever.ZonedDateTime,
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


class SQLCertificationRepo(ICertificationRepo):
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_certifications_for_employee(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
    ) -> list[EmployeeCertificationData]:
        """Fetches all certification records for an employee from the database."""
        stmt = select(EmployeeCertificationModel).where(
            EmployeeCertificationModel.org_id == org_id,
            EmployeeCertificationModel.employee_id == employee_id,
        )

        result = await self.db_session.scalars(stmt)
        records = result.all()

        return [
            EmployeeCertificationData(
                employee_id=r.id,
                certification_name=str(r.certification_name),
                # Mapping stored dates to whenever.Date
                acquired_date=whenever.Date(
                    r.acquired_date.year, r.acquired_date.month, r.acquired_date.day
                )
                if r.acquired_date
                else None,
                expiration_date=whenever.Date(
                    r.expiration_date.year,
                    r.expiration_date.month,
                    r.expiration_date.day,
                )
                if r.expiration_date
                else None,
            )
            for r in records
        ]
