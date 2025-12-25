import whenever

from snf_schedule_optimizer.models import DomainPrimaryKeyType
from snf_schedule_optimizer.services.hr.interfaces import (
    ICertificationRepo,
    ICertificationService,
)


class CertificationService(ICertificationService):
    """
    DOMAIN SERVICE: Contains pure business logic for certification validation.
    Decoupled from SQLAlchemy by using the ICertificationRetriever port.
    """

    def __init__(self, repo: ICertificationRepo):
        self.repo = repo

    async def is_certification_active(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        certification_name: str,
        check_date: whenever.ZonedDateTime,
    ) -> bool:
        """
        Business Rule: A certification is active if the check_date falls
        between the acquired_date and the expiration_date inclusive.
        """
        # 1. Fetch raw data via the retriever
        certs = await self.repo.get_certifications_for_employee(
            org_id,
            employee_id,
        )

        # 2. Extract the comparison date
        target_date = check_date.date()

        # 3. Apply Domain Logic
        for cert in certs:
            if cert.certification_name.upper() == certification_name.upper():
                # Check Start Boundary (If we have an acquisition date)
                if cert.acquired_date and target_date < cert.acquired_date:
                    continue

                # Check End Boundary (Expiration)
                # If expiration is None, it's considered a lifetime certification.
                if cert.expiration_date is None or cert.expiration_date >= target_date:
                    return True

        return False
