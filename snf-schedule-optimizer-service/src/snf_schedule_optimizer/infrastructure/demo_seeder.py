from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.domain.hr.interfaces import (
    IEmployeeRepo,
    IStaffCompensationRepo,
)
from snf_schedule_optimizer.domain.repositories import IFacilityRepo, IShiftRepo
from snf_schedule_optimizer.infrastructure.scenario_builder import ScenarioBuilder
from snf_schedule_optimizer.persistence import INurseRepo


class DemoSeeder:
    """
    Orchestrates the creation of a demo dataset using domain objects
    and clean Repo interfaces.
    """

    def __init__(
        self,
        employee_repo: IEmployeeRepo,
        nurse_repo: INurseRepo,
        shift_repo: IShiftRepo,
        comp_repo: IStaffCompensationRepo,
        facility_repo: IFacilityRepo,
        db_session: AsyncSession,
    ):
        self.employee_repo = employee_repo
        self.nurse_repo = nurse_repo
        self.shift_repo = shift_repo
        self.comp_repo = comp_repo
        self.facility_repo = facility_repo
        self.db_session = db_session

    async def seed_from_scenario(self, seed: int = 42) -> None:
        """
        Generates domain entities via the ScenarioBuilder and persists
        them through the Repo Ports.
        """
        # 1. Generate Domain Scenario
        scenario_builder = ScenarioBuilder(seed=seed)
        scenario = scenario_builder.build()

        # 2. Persist Facility Configurations
        # critical for timezone resolution and OT rules
        for config in scenario.facility_configs:
            await self.facility_repo.save_config(config)

        # 3. Persist Employees
        for emp in scenario.employees:
            await self.employee_repo.save_employee(
                scenario_builder.org_id,
                emp,
            )

        # 3. Persist Nurse Profiles & Preferences
        for nurse in scenario.nurses:
            await self.nurse_repo.save_nurse_profile(
                scenario_builder.org_id,
                nurse,
            )

        # 4. Persist Shifts
        for shift in scenario.shifts:
            await self.shift_repo.save_shift(scenario_builder.org_id, shift)

        # 5. Persist Financials
        for record in scenario.financials:
            await self.comp_repo.save_compensation_record(
                scenario_builder.org_id,
                record,
            )

        await self.db_session.commit()
