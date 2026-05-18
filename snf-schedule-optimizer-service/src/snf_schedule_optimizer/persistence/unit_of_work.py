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


class SqlAlchemyUnitOfWork(IUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._closed = False

    async def _ensure_session(self) -> AsyncSession:
        if self._session is None:
            self._session = self._session_factory()
            self._wire_repos()
        return self._session

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

    async def commit(self) -> None:
        if self._session is not None:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()

    async def close(self) -> None:
        if self._session is not None and not self._closed:
            await self._session.close()
            self._closed = True

    async def __aenter__(self) -> IUnitOfWork:
        await self._ensure_session()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
