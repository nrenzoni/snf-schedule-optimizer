import abc

import whenever

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    Employee,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.models.persistence_dtos import EmployeeCertificationData


class IEmployeeRepo(abc.ABC):
    """Defines the contract for retrieving core Employee identity records."""

    @abc.abstractmethod
    async def get_employee_by_id(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
    ) -> Employee | None:
        """
        Retrieves a single Employee record by their unique ID.
        """
        pass

    @abc.abstractmethod
    async def get_all_employees(
        self,
        org_id: DomainPrimaryKeyType,
    ) -> list[Employee]:
        """Retrieves all active Employee records."""
        pass

    @abc.abstractmethod
    async def save_employee(
        self,
        org_id: DomainPrimaryKeyType,
        employee: Employee,
    ) -> None:
        """Persists a domain Employee object."""
        pass


class IStaffCompensationRepo(abc.ABC):
    """Defines the contract for retrieving the active financial rate for an employee."""

    @abc.abstractmethod
    async def get_record_for_date(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        check_date: whenever.Date,
    ) -> StaffCompensationRecord | None:
        """
        Retrieves the one StaffCompensationRecord whose validity period
        covers the check_date.
        """
        pass

    @abc.abstractmethod
    async def get_all_records_for_org(
        self,
        org_id: DomainPrimaryKeyType,
        check_date: whenever.Date,
    ) -> dict[DomainPrimaryKeyType, StaffCompensationRecord]:
        """
        Retrieves compensation records for all active employees in a single query.
        Returns dict keyed by employee_id.
        """
        pass

    @abc.abstractmethod
    async def save_compensation_record(
        self,
        org_id: DomainPrimaryKeyType,
        record: StaffCompensationRecord,
    ) -> None:
        """Persists a domain StaffCompensationRecord."""
        pass


class ICertificationService(abc.ABC):
    @abc.abstractmethod
    async def is_certification_active(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
        certification_name: str,
        check_date: whenever.ZonedDateTime,
    ) -> bool:
        """Checks if the named certification is valid/unexpired on the check_date."""
        pass


class ICertificationRepo(abc.ABC):
    """PORT: Interface for fetching raw certification data."""

    @abc.abstractmethod
    async def get_certifications_for_employee(
        self,
        org_id: DomainPrimaryKeyType,
        employee_id: DomainPrimaryKeyType,
    ) -> list[EmployeeCertificationData]:
        pass
