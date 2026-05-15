"""Tests for constraint strategy composition / rule wiring."""

from typing import Any, cast

import pulp
import whenever

from snf_schedule_optimizer.models import (
    FacilityConfig,
    NurseProfile,
    OptimizationSettings,
    Shift,
)
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    ConsecutiveDaysLimitConstraintStrategy,
    ConsecutiveShiftFatigueStrategy,
    MaxShiftLengthConstraintStrategy,
    MaxWeeklyHoursConstraintStrategy,
)

from ..support.factories import make_shift


class _FakeFacilityProvider:
    def __init__(self, shifts: list[Shift], nurses: list[NurseProfile]) -> None:
        self._shifts = shifts
        self._nurses = nurses
        self._config = FacilityConfig(
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
        )

    def get_shifts_for_facility(self, fid: int) -> list[Shift]:
        return [s for s in self._shifts if s.facility_id == fid]

    async def get_nurses_for_shift(self, shift: Shift) -> list[NurseProfile]:
        return self._nurses

    def get_optimization_settings(self) -> OptimizationSettings:
        return OptimizationSettings()

    async def get_employee_states(self) -> dict[int, Any]:
        return {}

    def get_facility_config(self, fid: int) -> object:
        return self._config

    async def get_accumulated_hours_for_pay_period(self, eid: int) -> float:
        return 0.0


async def test_all_production_rule_strategies_are_instantiable() -> None:
    """Verify all four production rule strategies can be instantiated without error."""
    shift = make_shift()
    nurses = [NurseProfile(1, 40, ["CNA"], [])]
    provider = _FakeFacilityProvider([shift], nurses)
    lp = LpNurseShiftVariableHolder()
    lp.add_variable(shift, 1)
    problem = pulp.LpProblem("rule-instantiation", pulp.LpMinimize)

    strategies = [
        ConsecutiveShiftFatigueStrategy(),
        MaxShiftLengthConstraintStrategy(),
        MaxWeeklyHoursConstraintStrategy(),
        ConsecutiveDaysLimitConstraintStrategy(),
    ]
    for strategy in strategies:
        result = await strategy.apply_constraints(
            problem, lp, cast(IScenarioDataProvider, provider), facility_id=1
        )
        assert result is None
