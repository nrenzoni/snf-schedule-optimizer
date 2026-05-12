import datetime
from collections import defaultdict

import whenever
from sqlalchemy.ext.asyncio import AsyncSession

from snf_schedule_optimizer.domain.hr.interfaces import (
    IEmployeeRepo,
    IStaffCompensationRepo,
)
from snf_schedule_optimizer.domain.repositories import IFacilityRepo, IShiftRepo
from snf_schedule_optimizer.domain.scheduling.interfaces import IScheduleRepo
from snf_schedule_optimizer.infrastructure.scenario_builder import ScenarioBuilder
from snf_schedule_optimizer.models import (
    NurseProfile,
    Schedule,
    Shift,
    ShiftAssignmentsType,
    ShiftKey,
)
from snf_schedule_optimizer.models.scenario_models import TimeConfig, WorkforceConfig
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
        schedule_repo: IScheduleRepo,
        db_session: AsyncSession,
    ):
        self.employee_repo = employee_repo
        self.nurse_repo = nurse_repo
        self.shift_repo = shift_repo
        self.comp_repo = comp_repo
        self.facility_repo = facility_repo
        self.schedule_repo = schedule_repo
        self.db_session = db_session

    async def seed_from_scenario(self, seed: int = 42) -> None:
        """
        Generates domain entities via the ScenarioBuilder and persists
        them through the Repo Ports.
        """
        # 1. Generate Domain Scenario
        start_date, num_days = self._demo_window()
        scenario_builder = (
            ScenarioBuilder(seed=seed)
            .with_time(TimeConfig(start_date=start_date, num_days=num_days))
            .with_workforce(
                WorkforceConfig(
                    count_rn=42,
                    count_lpn=38,
                    count_cna=96,
                    percent_agency_rn=0.16,
                    percent_agency_lpn=0.18,
                    percent_agency_cna=0.24,
                )
            )
        )
        scenario_builder.org_id = 1000
        scenario_builder.facility_id = 1001
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

        await self.schedule_repo.save_schedule(
            self._build_demo_schedule(
                org_id=scenario_builder.org_id,
                facility_id=scenario_builder.facility_id,
                shifts=scenario.shifts,
                nurses=scenario.nurses,
            )
        )

        await self.db_session.commit()

    @staticmethod
    def _demo_window() -> tuple[whenever.ZonedDateTime, int]:
        today = datetime.date.today()
        first_this_month = today.replace(day=1)
        start = DemoSeeder._add_months(first_this_month, -1)
        end = DemoSeeder._add_months(start, 3)
        num_days = (end - start).days
        return whenever.ZonedDateTime(
            start.year,
            start.month,
            start.day,
            tz="America/New_York",
        ), num_days

    @staticmethod
    def _add_months(value: datetime.date, months: int) -> datetime.date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        return datetime.date(year, month, 1)

    def _build_demo_schedule(
        self,
        org_id: int,
        facility_id: int,
        shifts: list[Shift],
        nurses: list[NurseProfile],
    ) -> Schedule:
        assignments: ShiftAssignmentsType = defaultdict(list)
        rn_ids = [nurse.employee_id for nurse in nurses if "RN" in (nurse.skills or [])]
        lpn_ids = [nurse.employee_id for nurse in nurses if "LPN" in (nurse.skills or [])]
        cna_ids = [nurse.employee_id for nurse in nurses if "CNA" in (nurse.skills or [])]
        if not rn_ids and not lpn_ids and not cna_ids:
            return Schedule(org_id=org_id, facility_id=facility_id, schedule_id=1)

        unit_staffing = {
            101: {1: (1, 2, 6), 2: (1, 2, 5), 3: (1, 1, 3)},  # Rehab
            102: {1: (1, 2, 7), 2: (1, 2, 6), 3: (1, 1, 4)},  # LTC
            103: {1: (1, 1, 6), 2: (1, 1, 5), 3: (0, 1, 4)},  # Memory
            104: {1: (1, 2, 5), 2: (1, 1, 4), 3: (1, 1, 3)},  # Subacute
        }

        def add_staff(pool: list[int], count: int, start: int, shift_key: ShiftKey) -> None:
            if not pool:
                return
            for offset in range(count):
                assignments[shift_key].append(pool[(start + offset) % len(pool)])

        # Create a deterministic baseline rotation with realistic SNF coverage pressure.
        for index, shift in enumerate(shifts):
            rn_count, lpn_count, cna_count = unit_staffing.get(shift.unit_id or 0, {}).get(
                shift.shift_number,
                (1, 1, 4),
            )
            is_weekend = shift.day_of_week in {whenever.Weekday(6), whenever.Weekday(7)}
            if is_weekend and shift.shift_number in {2, 3}:
                cna_count = max(2, cna_count - 1)
            if shift.shift_number == 3 and is_weekend:
                rn_count = max(1, rn_count - 1)

            add_staff(rn_ids, rn_count, index, shift.shift_key)
            add_staff(lpn_ids, lpn_count, index * 2, shift.shift_key)
            add_staff(cna_ids, cna_count, index * 3, shift.shift_key)

        return Schedule(
            org_id=org_id,
            facility_id=facility_id,
            schedule_id=1,
            shift_assignments=dict(assignments),
        )
