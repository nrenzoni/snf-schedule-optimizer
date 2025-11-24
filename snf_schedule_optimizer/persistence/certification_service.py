import abc

import pendulum
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
import pendulum

from snf_schedule_optimizer.services.interfaces import ICertificationService
from snf_schedule_optimizer.sqlalchemy_models.employee_certification import EmployeeCertificationModel


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
