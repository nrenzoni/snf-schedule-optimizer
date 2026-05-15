from unittest.mock import AsyncMock, MagicMock

import whenever

from snf_schedule_optimizer.domain.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.domain.payroll.calculations.shift_slicers import (
    TimeOverlapShiftSlicer,
)
from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    PreferenceWeights,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.calculators import NurseHardBlockCheckerImpl
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    HprdStaffingConstraintStrategy,
)
from snf_schedule_optimizer.optimizer.strategies.pay import (
    BiWeeklyPayPeriodOTStrategy,
    WeeklyVolumePayStrategy,
)
from snf_schedule_optimizer.optimizer.strategies.variables import (
    CoreVariableGenerationStrategy,
)
from snf_schedule_optimizer.persistence.fakes import (
    FakeEmployeeRepo,
    FakeHprdRequirementCalculator,
    FakeMLModelRepo,
    FakeNurseRepo,
    FakeStaffCompensationRepo,
    FakeWorkHistoryService,
)

tz_ny = "America/New_York"


def _make_shifts(
    ref: whenever.ZonedDateTime, n_days: int, hours_per_shift: float = 12.0
) -> list[Shift]:
    shifts: list[Shift] = []
    for day_offset in range(n_days):
        day = ref.add(days=day_offset)
        start = whenever.ZonedDateTime(day.year, day.month, day.day, 7, tz=tz_ny)
        end = start.add(hours=hours_per_shift)
        shift = Shift(
            org_id=1,
            shift_key=ShiftKey(facility_id=1, shift_id=day_offset + 1),
            shift_number=1,
            day_shift=True,
            day_of_week=start.date().day_of_week(),
            shift_start_dt=start,
            shift_end_dt=end,
            unit_id=None,
            is_scheduled=True,
        )
        shifts.append(shift)
    return shifts


def _make_pay_processor(comp: StaffCompensationRecord) -> ShiftPayProcessor:
    mock_eligibility = MagicMock()
    mock_eligibility.get_applicable_rules = AsyncMock(return_value=([], []))
    return ShiftPayProcessor(
        eligibility_service=mock_eligibility,
        slicer=TimeOverlapShiftSlicer(),
        compensation_service=FakeStaffCompensationRepo([comp]),
    )


async def test_biweekly_ot_fires_when_total_exceeds_80h() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)
    shifts = _make_shifts(ref, 8)

    nurse_emp = Employee(
        employee_id=1,
        name="RN A",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    nurse_profile = NurseProfile(
        employee_id=1,
        available_hours_weekly=80,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    pay_processor = _make_pay_processor(comp)

    fake_hprd = FakeHprdRequirementCalculator(
        {(s.shift_id, HprdEnforcedRole.RN): 1.0 for s in shifts}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[
            WeeklyVolumePayStrategy(
                shift_pay_processor=pay_processor,
                threshold=40.0,
            ),
            BiWeeklyPayPeriodOTStrategy(threshold=80.0),
        ],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([nurse_emp]),
        nurse_retriever=FakeNurseRepo([nurse_profile]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=shifts,
                config=FacilityConfig(
                    org_id=1,
                    facility_id=1,
                    shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0,
                    night_shift_multiplier=1.0,
                    tz=tz_ny,
                ),
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.statistics is not None
    assert result.statistics.objective_value is not None
    assert result.optimal_schedule is not None

    assignments = result.optimal_schedule.shift_assignments
    assert assignments is not None
    assigned_hours = sum(
        shift.duration_hours
        for shift_key, emp_ids in assignments.items()
        for shift in shifts
        if shift.shift_key == shift_key
        for _ in emp_ids
    )

    assert assigned_hours > 80, (
        f"Expected >80h assigned to trigger bi-weekly OT, got {assigned_hours}"
    )


async def test_biweekly_ot_does_not_fire_below_threshold() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)
    shifts = _make_shifts(ref, 5)

    nurse_emp = Employee(
        employee_id=1,
        name="RN A",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    nurse_profile = NurseProfile(
        employee_id=1,
        available_hours_weekly=80,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    pay_processor = _make_pay_processor(comp)

    fake_hprd = FakeHprdRequirementCalculator(
        {(s.shift_id, HprdEnforcedRole.RN): 1.0 for s in shifts}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[
            WeeklyVolumePayStrategy(
                shift_pay_processor=pay_processor,
                threshold=40.0,
            ),
            BiWeeklyPayPeriodOTStrategy(threshold=80.0),
        ],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([nurse_emp]),
        nurse_retriever=FakeNurseRepo([nurse_profile]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=shifts,
                config=FacilityConfig(
                    org_id=1,
                    facility_id=1,
                    shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0,
                    night_shift_multiplier=1.0,
                    tz=tz_ny,
                ),
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.statistics is not None
    assert result.statistics.objective_value is not None
    assert result.optimal_schedule is not None

    assignments = result.optimal_schedule.shift_assignments
    assert assignments is not None
    assigned_hours = sum(
        shift.duration_hours
        for shift_key, emp_ids in assignments.items()
        for shift in shifts
        if shift.shift_key == shift_key
        for _ in emp_ids
    )

    assert assigned_hours <= 80, (
        f"Expected <= 80h, no bi-weekly OT needed, got {assigned_hours}"
    )
