"""Tests for locked assignment constraint strategy."""

from typing import cast

import pulp

from snf_schedule_optimizer.models import (
    LockedAssignment,
    Shift,
)
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.optimizer.strategies.fixing import (
    LockedAssignmentConstraintStrategy,
)

from ..support.factories import make_shift


class _FakeDataProvider:
    def __init__(self, shifts: list[Shift]) -> None:
        self._shifts = shifts

    def get_shifts_for_facility(self, facility_id: int) -> list[Shift]:
        return [s for s in self._shifts if s.facility_id == facility_id]

    def get_facility_config(self, facility_id: int) -> object:
        return None

    def get_optimization_settings(self) -> object:
        from snf_schedule_optimizer.models import OptimizationSettings

        return OptimizationSettings()


async def test_locked_assignment_forces_variable_to_one() -> None:
    shift = make_shift()
    lp_holder = LpNurseShiftVariableHolder()
    v = lp_holder.add_variable(shift, 1)
    problem = pulp.LpProblem("lock-test", pulp.LpMinimize)

    strategy = LockedAssignmentConstraintStrategy(
        [LockedAssignment(employee_id=1, shift_key=shift.shift_key)]
    )
    await strategy.apply_constraints(
        problem,
        lp_holder,
        cast(IScenarioDataProvider, _FakeDataProvider([shift])),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 1
    assert constraints[0].get(v, None) is not None


async def test_locked_assignment_does_not_force_other_variables() -> None:
    shift = make_shift()
    lp_holder = LpNurseShiftVariableHolder()
    v1 = lp_holder.add_variable(shift, 1)
    v2 = lp_holder.add_variable(shift, 2)
    problem = pulp.LpProblem("lock-partial", pulp.LpMinimize)

    strategy = LockedAssignmentConstraintStrategy(
        [LockedAssignment(employee_id=1, shift_key=shift.shift_key)]
    )
    await strategy.apply_constraints(
        problem,
        lp_holder,
        cast(IScenarioDataProvider, _FakeDataProvider([shift])),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 1
    c = constraints[0]
    assert c.get(v1, None) is not None
    assert c.get(v2, None) is None


async def test_locked_assignment_for_wrong_facility_skipped() -> None:
    shift_f1 = make_shift(facility_id=1, shift_id=101)
    shift_f2 = make_shift(facility_id=2, shift_id=201)
    lp_holder = LpNurseShiftVariableHolder()
    v1 = lp_holder.add_variable(shift_f1, 1)
    v2 = lp_holder.add_variable(shift_f2, 1)
    problem = pulp.LpProblem("lock-facility", pulp.LpMinimize)

    strategy = LockedAssignmentConstraintStrategy(
        [LockedAssignment(employee_id=1, shift_key=shift_f1.shift_key)]
    )
    await strategy.apply_constraints(
        problem,
        lp_holder,
        cast(IScenarioDataProvider, _FakeDataProvider([shift_f1, shift_f2])),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 1
    c = constraints[0]
    assert c.get(v1, None) is not None
    assert c.get(v2, None) is None


async def test_multiple_locked_assignments_both_enforced() -> None:
    shift_1 = make_shift(facility_id=1, shift_id=101, start_hour=7)
    shift_2 = make_shift(facility_id=1, shift_id=102, start_hour=19)
    lp_holder = LpNurseShiftVariableHolder()
    lp_holder.add_variable(shift_1, 1)
    lp_holder.add_variable(shift_2, 1)
    problem = pulp.LpProblem("lock-multi", pulp.LpMinimize)

    strategy = LockedAssignmentConstraintStrategy(
        [
            LockedAssignment(employee_id=1, shift_key=shift_1.shift_key),
            LockedAssignment(employee_id=1, shift_key=shift_2.shift_key),
        ]
    )
    await strategy.apply_constraints(
        problem,
        lp_holder,
        cast(IScenarioDataProvider, _FakeDataProvider([shift_1, shift_2])),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 2


async def test_empty_locked_list_is_noop() -> None:
    shift = make_shift()
    lp_holder = LpNurseShiftVariableHolder()
    lp_holder.add_variable(shift, 1)
    problem = pulp.LpProblem("lock-empty", pulp.LpMinimize)

    strategy = LockedAssignmentConstraintStrategy([])
    await strategy.apply_constraints(
        problem,
        lp_holder,
        cast(IScenarioDataProvider, _FakeDataProvider([shift])),
        facility_id=1,
    )
    constraints = list(problem.constraints.values())
    assert len(constraints) == 0
