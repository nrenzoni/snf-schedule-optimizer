from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.models import Employee
from snf_schedule_optimizer.services.hr.interfaces import IEmployeeRetriever
from snf_schedule_optimizer.sqlalchemy_models.employee import EmployeeModel


class EmployeeRetrieverStaticListImpl(IEmployeeRetriever):
    """
    Concrete implementation that retrieves Employee objects from a static,
    in-memory list (used for testing).
    """

    def __init__(self, employees: list[Employee]):
        # Store the list of Employee objects and create a lookup map
        self.employee_list = employees
        self.employee_map = {e.employee_id: e for e in employees}

    async def get_employee_by_id(
        self,
        org_id: str,
        employee_id: str,
    ) -> Employee | None:
        """
        Retrieves a single Employee record by their unique ID.
        """
        return self.employee_map.get(employee_id)

    async def get_all_employees(
        self,
        org_id: str,
    ) -> list[Employee]:
        """Retrieves all active Employee records."""
        return self.employee_list


class SQLEmployeeRetriever(IEmployeeRetriever):
    """
    SQLAlchemy implementation of IEmployeeRetriever.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_employee_by_id(
        self,
        org_id: str,
        employee_id: str,
    ) -> Employee | None:
        stmt = select(EmployeeModel).where(
            and_(
                EmployeeModel.org_id == org_id,
                EmployeeModel.employee_id == employee_id,
            )
        )
        result: EmployeeModel | None = await self.db_session.scalar(stmt)

        if result:
            return result.to_domain()
        return None

    async def get_all_employees(
        self,
        org_id: str,
    ) -> list[Employee]:
        """
        Retrieves all active Employee records.
        """
        stmt = select(EmployeeModel).where(
            EmployeeModel.org_id == org_id,
        )
        results = (await self.db_session.scalars(stmt)).all()

        return [row.to_domain() for row in results]
