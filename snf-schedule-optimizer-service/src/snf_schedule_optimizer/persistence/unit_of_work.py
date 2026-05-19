"""Unit of Work pattern for coordinating persistence operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from snf_schedule_optimizer.domain.hr.interfaces import (
    ICertificationRepo,
    IEmployeeRepo,
    IStaffCompensationRepo,
)
from snf_schedule_optimizer.domain.payroll.interfaces import (
    IDifferentialRuleRepo,
    IEmployeeRulesRepo,
    IFacilityRulesRepo,
    IOvertimeRuleRepo,
)
from snf_schedule_optimizer.domain.repositories import IFacilityRepo, IShiftRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import (
    IScheduleRepo,
    IShiftRequirementsRepo,
)
from snf_schedule_optimizer.domain.timekeeping.interfaces import IRawHistoryRepo
from snf_schedule_optimizer.persistence import (
    INurseRepo,
    SQLCertificationRepo,
    SQLDifferentialRuleRepo,
    SQLNurseRepo,
    SQLOvertimeRuleRepo,
    SQLShiftRequirementsRepo,
)
from snf_schedule_optimizer.persistence.employee_repo import SQLEmployeeRepo
from snf_schedule_optimizer.persistence.employee_rule_repo import SQLEmployeeRulesRepo
from snf_schedule_optimizer.persistence.facility_repo import SQLFacilityRepo
from snf_schedule_optimizer.persistence.facility_rules_repo import SQLFacilityRulesRepo
from snf_schedule_optimizer.persistence.history_repo import SQLRawHistoryRepo
from snf_schedule_optimizer.persistence.resident_acuity_per_shift_repo import (
    SQLResidentAcuityPerShiftRepo,
)
from snf_schedule_optimizer.persistence.schedule_repo import SQLScheduleRepo
from snf_schedule_optimizer.persistence.shift_repo import SQLShiftRepo
from snf_schedule_optimizer.persistence.staff_compensation_repo import (
    SQLStaffCompensationRepo,
)
from snf_schedule_optimizer.resident_acuity_repo import IResidentAcuityPerShiftRepo


class IUnitOfWork(ABC):
    shift_repo: IShiftRepo
    schedule_repo: IScheduleRepo
    facility_repo: IFacilityRepo
    employee_repo: IEmployeeRepo
    nurse_repo: INurseRepo
    certification_repo: ICertificationRepo
    history_repo: IRawHistoryRepo
    compensation_repo: IStaffCompensationRepo
    differential_rule_repo: IDifferentialRuleRepo
    overtime_rule_repo: IOvertimeRuleRepo
    facility_rules_repo: IFacilityRulesRepo
    employee_rules_repo: IEmployeeRulesRepo
    shift_requirements_repo: IShiftRequirementsRepo
    acuity_repo: IResidentAcuityPerShiftRepo

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


class AsyncUnitOfWork(IUnitOfWork):
    """Manages a SQLAlchemy async session + transaction for a single business operation."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> AsyncUnitOfWork:
        self._session = self._session_factory()
        await self._session.begin()
        self._wire_repos()
        return self

    async def commit(self) -> None:
        if self._session is not None:
            await self._session.commit()
            self._committed = True

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aexit__(self, *args: Any) -> None:
        try:
            if self._session is not None and not self._committed:
                await self._session.rollback()
        finally:
            await self.close()

    def _wire_repos(self) -> None:
        assert self._session is not None
        s = self._session
        self.shift_repo = SQLShiftRepo(s)
        self.schedule_repo = SQLScheduleRepo(db_session=s)
        self.facility_repo = SQLFacilityRepo(session=s)
        self.employee_repo = SQLEmployeeRepo(db_session=s)
        self.nurse_repo = SQLNurseRepo(session=s)
        self.certification_repo = SQLCertificationRepo(db_session=s)
        self.history_repo = SQLRawHistoryRepo(db_session=s)
        self.compensation_repo = SQLStaffCompensationRepo(db_session=s)
        self.differential_rule_repo = SQLDifferentialRuleRepo(session=s)
        self.overtime_rule_repo = SQLOvertimeRuleRepo(session=s)
        self.facility_rules_repo = SQLFacilityRulesRepo(db_session=s)
        self.employee_rules_repo = SQLEmployeeRulesRepo(db_session=s)
        self.shift_requirements_repo = SQLShiftRequirementsRepo(db_session=s)
        self.acuity_repo = SQLResidentAcuityPerShiftRepo(db_session=s)


class UnitOfWorkFactory:
    """Factory that produces AsyncUnitOfWork instances from a session factory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    def __call__(self) -> AsyncUnitOfWork:
        return AsyncUnitOfWork(self._session_factory)
