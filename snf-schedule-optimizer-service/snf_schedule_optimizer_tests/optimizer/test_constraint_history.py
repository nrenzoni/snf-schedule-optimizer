"""I.2: Verify history-aware rest/fatigue constraints fire with populated states."""

import whenever

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
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    ConsecutiveDaysLimitConstraintStrategy,
    ConsecutiveShiftFatigueStrategy,
    HprdStaffingConstraintStrategy,
    MaxShiftLengthConstraintStrategy,
    MaxWeeklyHoursConstraintStrategy,
)
from snf_schedule_optimizer.optimizer.strategies.variables import (
    CoreVariableGenerationStrategy,
)
from snf_schedule_optimizer.optimizer.calculators import NurseHardBlockCheckerImpl
from snf_schedule_optimizer.persistence.fakes import (
    FakeEmployeeRepo,
    FakeHprdRequirementCalculator,
    FakeMLModelRepo,
    FakeNurseRepo,
    FakeStaffCompensationRepo,
    FakeWorkHistoryService,
)
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory

tz_ny = "America/New_York"


async def test_history_rest_blocks_employee_below_min_gap() -> None:
    """
    Employee ended previous shift at 11pm. First decision shift starts at 7am.
    Gap = 8h < min_rest (10h). Employee should be blocked from first shift
    but available for second shift (16h gap).
    """
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    tired_emp = Employee(
        employee_id=1, name="Tired RN", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )
    fresh_emp = Employee(
        employee_id=2, name="Fresh RN", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )

    tired_nurse = NurseProfile(
        employee_id=1, available_hours_weekly=40, skills=["RN"], shift_custom_preferences=[]
    )
    fresh_nurse = NurseProfile(
        employee_id=2, available_hours_weekly=40, skills=["RN"], shift_custom_preferences=[]
    )

    comp = StaffCompensationRecord(
        employee_id=1, base_rate_effective=30.0, ot_multiplier=1.5,
        is_agency=False, effective_start_date=whenever.Date(2024, 1, 1),
    )
    comp2 = StaffCompensationRecord(
        employee_id=2, base_rate_effective=30.0, ot_multiplier=1.5,
        is_agency=False, effective_start_date=whenever.Date(2024, 1, 1),
    )

    shift_1 = Shift(
        org_id=1, shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1, day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None, is_scheduled=True,
    )
    shift_2 = Shift(
        org_id=1, shift_key=ShiftKey(facility_id=1, shift_id=2),
        shift_number=2, day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref.add(hours=16),
        shift_end_dt=ref.add(hours=24),
        unit_id=None, is_scheduled=True,
    )

    prev_end = ref.subtract(hours=8)
    prev_end_iso = prev_end.format_iso()

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={
            (1, HprdEnforcedRole.RN): 1.0,
            (2, HprdEnforcedRole.RN): 1.0,
        }
    )

    history_service = FakeWorkHistoryService(
        accumulated_hours_map={1: 8.0, 2: 0.0},
        last_shift_end_map={1: prev_end_iso},
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            ConsecutiveShiftFatigueStrategy(),
            ConsecutiveDaysLimitConstraintStrategy(),
            MaxShiftLengthConstraintStrategy(),
            MaxWeeklyHoursConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([tired_emp, fresh_emp]),
        nurse_retriever=FakeNurseRepo([tired_nurse, fresh_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp, comp2]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=history_service,
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift_1, shift_2],
                config=FacilityConfig(
                    org_id=1, facility_id=1, shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0, night_shift_multiplier=1.0, tz=tz_ny,
                ),
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(min_rest_period=10),
    )

    result = await optimizer.solve(
        data_provider=provider, preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments

    shift_1_staff = assignments.get(ShiftKey(1, 1), [])
    shift_2_staff = assignments.get(ShiftKey(1, 2), [])

    assert 1 not in shift_1_staff, (
        "Tired employee should be blocked from shift 1 (8h gap < 10h min_rest)"
    )
    assert 1 in shift_2_staff, (
        "Tired employee should be assigned to shift 2 (16h gap > 10h min_rest)"
    )
    assert 2 in shift_1_staff, "Fresh employee should cover shift 1"


async def test_consecutive_days_limit_blocks_at_max() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    burnt_emp = Employee(
        employee_id=3, name="Burnt RN", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )
    fresh_emp = Employee(
        employee_id=4, name="Fresh RN", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )
    burnt_nurse = NurseProfile(
        employee_id=3, available_hours_weekly=40, skills=["RN"], shift_custom_preferences=[]
    )
    fresh_nurse = NurseProfile(
        employee_id=4, available_hours_weekly=40, skills=["RN"], shift_custom_preferences=[]
    )
    comp = StaffCompensationRecord(
        employee_id=3, base_rate_effective=30.0, ot_multiplier=1.5,
        is_agency=False, effective_start_date=whenever.Date(2024, 1, 1),
    )
    comp2 = StaffCompensationRecord(
        employee_id=4, base_rate_effective=30.0, ot_multiplier=1.5,
        is_agency=False, effective_start_date=whenever.Date(2024, 1, 1),
    )

    shift = Shift(
        org_id=1, shift_key=ShiftKey(facility_id=1, shift_id=10),
        shift_number=1, day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None, is_scheduled=True,
    )

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={(10, HprdEnforcedRole.RN): 1.0}
    )

    history_service = FakeWorkHistoryService(
        accumulated_hours_map={3: 0.0, 4: 0.0},
        consecutive_days_map={3: 5, 4: 0},
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            ConsecutiveDaysLimitConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([burnt_emp, fresh_emp]),
        nurse_retriever=FakeNurseRepo([burnt_nurse, fresh_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp, comp2]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=history_service,
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1, shifts=[shift],
                config=FacilityConfig(
                    org_id=1, facility_id=1, shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0, night_shift_multiplier=1.0, tz=tz_ny,
                    max_consecutive_work_days=5,
                ),
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider, preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments
    staff = assignments.get(ShiftKey(1, 10), [])

    assert 3 not in staff, (
        "Burnt nurse with 5 consecutive days should be blocked"
    )
    assert 4 in staff, (
        "Fresh nurse should be assigned instead"
    )
