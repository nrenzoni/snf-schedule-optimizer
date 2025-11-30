import abc
from typing import List, Optional

import pendulum

from snf_schedule_optimizer.models import Employee, StaffCompensationRecord


class IEmployeeRetriever(abc.ABC):
    """Defines the contract for retrieving core Employee identity records."""

    @abc.abstractmethod
    def get_employee_by_id(self, employee_id: str) -> Optional[Employee]:
        """Retrieves a single Employee record by their unique ID."""
        pass

    @abc.abstractmethod
    def get_all_employees(self) -> List[Employee]:
        """Retrieves all active Employee records."""
        pass


class IStaffCompensationService(abc.ABC):
    """Defines the contract for retrieving the active financial rate for an employee."""

    @abc.abstractmethod
    def get_record_for_date(
        self,
        employee_id: str,
        check_date: pendulum.DateTime,
    ) -> Optional[StaffCompensationRecord]:
        """
        Retrieves the one StaffCompensationRecord whose validity period
        covers the check_date.
        """
        pass


class ICertificationService(abc.ABC):
    @abc.abstractmethod
    def is_certification_active(
        self,
        employee_id: str,
        certification_name: str,
        check_date: pendulum.DateTime,
    ) -> bool:
        """Checks if the named certification is valid/unexpired on the check_date."""
        pass
