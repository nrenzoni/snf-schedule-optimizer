from snf_schedule_optimizer.models import Employee
from snf_schedule_optimizer.services.hr.interfaces import IEmployeeRetriever


class EmployeeRetrieverStaticListImpl(IEmployeeRetriever):
    """
    Concrete implementation that retrieves Employee objects from a static,
    in-memory list (used for testing).
    """

    def __init__(self, employees: list[Employee]):
        # Store the list of Employee objects and create a lookup map
        self.employee_list = employees
        self.employee_map = {e.employee_id: e for e in employees}

    def get_employee_by_id(self, employee_id: str) -> Employee | None:
        """Retrieves a single Employee record by their unique ID."""
        return self.employee_map.get(employee_id)

    def get_all_employees(self) -> list[Employee]:
        """Retrieves all active Employee records."""
        return self.employee_list
