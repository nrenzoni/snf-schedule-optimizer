import abc

import whenever

from snf_schedule_optimizer.models import Employee, StaffCompensationRecord


class IEmployeeRetriever(abc.ABC):
    """Defines the contract for retrieving core Employee identity records."""

    @abc.abstractmethod
    async def get_employee_by_id(
        self,
        org_id: str,
        employee_id: str,
    ) -> Employee | None:
        """
        Retrieves a single Employee record by their unique ID.
        """
        pass

    @abc.abstractmethod
    async def get_all_employees(
        self,
        org_id: str,
    ) -> list[Employee]:
        """Retrieves all active Employee records."""
        pass


class IStaffCompensationRetriever(abc.ABC):
    """Defines the contract for retrieving the active financial rate for an employee."""

    @abc.abstractmethod
    async def get_record_for_date(
        self,
        employee_id: str,
        check_date: whenever.ZonedDateTime,
    ) -> StaffCompensationRecord | None:
        """
        Retrieves the one StaffCompensationRecord whose validity period
        covers the check_date.
        """
        pass


class ICertificationService(abc.ABC):
    @abc.abstractmethod
    async def is_certification_active(
        self,
        employee_id: str,
        certification_name: str,
        check_date: whenever.ZonedDateTime,
    ) -> bool:
        """Checks if the named certification is valid/unexpired on the check_date."""
        pass
