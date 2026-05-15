"""Tests for history-aware constraint strategies."""

from typing import cast

import pulp
import whenever

from snf_schedule_optimizer.models import (
    EmployeeStateSnapshot,
    NurseProfile,
    OptimizationSettings,
    Shift,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    ConsecutiveDaysLimitConstraintStrategy,
    ConsecutiveShiftFatigueStrategy,
    MaxWeeklyHoursConstraintStrategy,
)


def _make_shift(fid: int = 1, sid: int = 101, start_hour: int = 7, start_day: int = 1, hours: int = 8) -> Shift:
    when = whenever.ZonedDateTime(2025, 1, start_day, start_hour, tz="America/New_York")
    return Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=fid, shift_id=sid),
        shift_number=1,
        day_shift=start_hour < 18,
        day_of_week=when.date().day_of_week(),
        shift_start_dt=when,
        shift_end_dt=when.add(hours=hours),
        unit_id=None,
        is_scheduled=True,
    )


class _FakeProvider:
    def __init__(
        self,
        shifts: list[Shift],
        nurses_map: dict[int, list[NurseProfile]] | None = None,
        employee_states: dict[int, EmployeeStateSnapshot] | None = None,
        settings: OptimizationSettings | None = None,
        accum_hours: dict[int, float] | None = None,
        config: object | None = None,
    ) -> None:
        self._shifts = shifts
        self._nurses_map = nurses_map or {}
        self._employee_states = employee_states or {}
        self._settings = settings or OptimizationSettings()
        self._accum_hours = accum_hours or {}
        self._config = config

    def get_shifts_for_facility(self, fid: int) -> list[Shift]:
        return [s for s in self._shifts if s.facility_id == fid]

    async def get_nurses_for_shift(self, shift: Shift) -> list[NurseProfile]:
        return self._nurses_map.get(shift.shift_id, [])

    async def get_employee_states(self) -> dict[int, EmployeeStateSnapshot]:
        return self._employee_states

    def get_optimization_settings(self) -> OptimizationSettings:
        return self._settings

    async def get_accumulated_hours_for_pay_period(self, eid: int) -> float:
        return self._accum_hours.get(eid, 0.0)

    def get_facility_config(self, fid: int) -> object:
        return self._config


async def test_fatigue_strategy_blocks_back_to_back_with_insufficient_rest() -> None:
    s1 = _make_shift(sid=101, start_hour=7, start_day=1, hours=12)
    s2 = _make_shift(sid=102, start_hour=15, start_day=1, hours=12)
    nurses = [
        NurseProfile(1, 40, ["CNA"], []),
        NurseProfile(2, 40, ["CNA"], []),
    ]
    provider = _FakeProvider(
        shifts=[s1, s2],
        nurses_map={
            s1.shift_id: nurses,
            s2.shift_id: nurses,
        },
        settings=OptimizationSettings(min_rest_period=10),
    )
    lp = LpNurseShiftVariableHolder()
    lp.add_variable(s1, 1)
    lp.add_variable(s2, 1)
    lp.add_variable(s1, 2)
    lp.add_variable(s2, 2)
    problem = pulp.LpProblem("fatigue-test", pulp.LpMinimize)

    strategy = ConsecutiveShiftFatigueStrategy()
    await strategy.apply_constraints(
        problem,
        lp,
        cast(IScenarioDataProvider, provider),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 2


async def test_fatigue_strategy_allows_with_sufficient_rest() -> None:
    s1 = _make_shift(sid=101, start_hour=7, start_day=1, hours=8)
    s2 = _make_shift(sid=102, start_hour=7, start_day=3, hours=8)
    nurses = [NurseProfile(1, 40, ["CNA"], [])]
    provider = _FakeProvider(
        shifts=[s1, s2],
        nurses_map={
            s1.shift_id: nurses,
            s2.shift_id: nurses,
        },
        settings=OptimizationSettings(min_rest_period=10),
    )
    lp = LpNurseShiftVariableHolder()
    lp.add_variable(s1, 1)
    lp.add_variable(s2, 1)
    problem = pulp.LpProblem("fatigue-ok", pulp.LpMinimize)

    strategy = ConsecutiveShiftFatigueStrategy()
    await strategy.apply_constraints(
        problem,
        lp,
        cast(IScenarioDataProvider, provider),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 0


async def test_max_weekly_hours_respects_history() -> None:
    s1 = _make_shift(sid=101, start_hour=7, start_day=1, hours=8)
    s2 = _make_shift(sid=102, start_hour=7, start_day=2, hours=8)
    nurse = NurseProfile(1, 40, ["CNA"], [])
    provider = _FakeProvider(
        shifts=[s1, s2],
        nurses_map={
            s1.shift_id: [nurse],
            s2.shift_id: [nurse],
        },
        accum_hours={1: 32.0},
        settings=OptimizationSettings(),
    )
    lp = LpNurseShiftVariableHolder()
    lp.add_variable(s1, 1)
    lp.add_variable(s2, 1)
    problem = pulp.LpProblem("hours-test", pulp.LpMinimize)

    strategy = MaxWeeklyHoursConstraintStrategy()
    await strategy.apply_constraints(
        problem,
        lp,
        cast(IScenarioDataProvider, provider),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 1


async def test_consecutive_days_limit_blocks_when_history_exceeds() -> None:
    s1 = _make_shift(sid=101, start_hour=7, start_day=1, hours=8)
    nurse = NurseProfile(1, 40, ["CNA"], [])
    provider = _FakeProvider(
        shifts=[s1],
        nurses_map={s1.shift_id: [nurse]},
        employee_states={1: EmployeeStateSnapshot(
            employee_id=1,
            worked_hours_week=0.0,
            worked_hours_pay_period=0.0,
            consecutive_days_worked=5,
            last_shift_end=None,
        )},
        config=whenever.Weekday.MONDAY,
    )
    from snf_schedule_optimizer.models import FacilityConfig
    provider._config = FacilityConfig(
        org_id=1,
        facility_id=1,
        shifts_per_day=3,
        overtime_threshold_hours_per_week=40,
        start_of_work_week_day=whenever.Weekday.MONDAY,
        start_of_work_day_time=whenever.Time(7, 0, 0),
        pay_period=whenever.DateDelta(weeks=1),
        weekend_multiplier=1.0,
        night_shift_multiplier=1.0,
        tz="America/New_York",
        max_consecutive_work_days=5,
    )
    lp = LpNurseShiftVariableHolder()
    lp.add_variable(s1, 1)
    problem = pulp.LpProblem("consec-test", pulp.LpMinimize)

    strategy = ConsecutiveDaysLimitConstraintStrategy()
    await strategy.apply_constraints(
        problem,
        lp,
        cast(IScenarioDataProvider, provider),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 1
