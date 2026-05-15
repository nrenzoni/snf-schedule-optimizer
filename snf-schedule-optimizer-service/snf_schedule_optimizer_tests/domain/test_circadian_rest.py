"""III.2: Circadian rest period constraint enforces longer rest after night shifts."""

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
from snf_schedule_optimizer.optimizer.calculators import NurseHardBlockCheckerImpl
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    ConsecutiveShiftFatigueStrategy,
    HprdStaffingConstraintStrategy,
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


async def test_longer_rest_after_night_shift() -> None:
    """Nurse works night (23:00-07:00), then day shift next day at 07:00 (0h rest) blocked.
    But day shift at 19:00 (12h rest >= 11h circadian) allowed."""
    ref = whenever.ZonedDateTime(2025, 1, 1, 23, tz=tz_ny)

    emp = Employee(
        employee_id=1,
        name="Night RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    backup_emp = Employee(
        employee_id=2,
        name="Backup RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )

    nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    backup_nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
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
    comp2 = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    night_shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=False,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    early_day = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=2),
        shift_number=2,
        day_shift=True,
        day_of_week=ref.add(hours=8).date().day_of_week(),
        shift_start_dt=ref.add(hours=8),
        shift_end_dt=ref.add(hours=16),
        unit_id=None,
        is_scheduled=True,
    )

    late_day = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=3),
        shift_number=3,
        day_shift=True,
        day_of_week=ref.add(hours=20).date().day_of_week(),
        shift_start_dt=ref.add(hours=20),
        shift_end_dt=ref.add(hours=28),
        unit_id=None,
        is_scheduled=True,
    )

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={
            (1, HprdEnforcedRole.RN): 1.0,
            (2, HprdEnforcedRole.RN): 1.0,
            (3, HprdEnforcedRole.RN): 1.0,
        }
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            ConsecutiveShiftFatigueStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([emp, backup_emp]),
        nurse_retriever=FakeNurseRepo([nurse, backup_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp, comp2]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[night_shift, early_day, late_day],
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
                    min_circadian_rest_after_night=11.0,
                ),
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(min_rest_period=10),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments

    night_staff = assignments.get(ShiftKey(1, 1), [])
    early_day_staff = assignments.get(ShiftKey(1, 2), [])
    late_day_staff = assignments.get(ShiftKey(1, 3), [])

    assert len(night_staff) >= 1, "Night shift must be covered"
    assert len(early_day_staff) >= 1, "Early day must be covered"

    night_nurse = night_staff[0]
    early_nurse = early_day_staff[0]

    assert night_nurse != early_nurse, (
        "Night nurse blocked from early day (0h gap < 11h circadian rest)"
    )

    assert night_nurse in late_day_staff, (
        "Night nurse allowed on late day (12h gap >= 11h circadian rest)"
    )


async def test_standard_rest_for_day_to_day() -> None:
    """Nurse works day (07:00-15:00), then next day at 07:00 (16h rest > 10h min); allowed."""
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    emp = Employee(
        employee_id=1,
        name="Day RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )

    nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
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

    day1 = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    day2 = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=2),
        shift_number=2,
        day_shift=True,
        day_of_week=ref.add(hours=24).date().day_of_week(),
        shift_start_dt=ref.add(hours=24),
        shift_end_dt=ref.add(hours=32),
        unit_id=None,
        is_scheduled=True,
    )

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={
            (1, HprdEnforcedRole.RN): 1.0,
            (2, HprdEnforcedRole.RN): 1.0,
        }
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            ConsecutiveShiftFatigueStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([emp]),
        nurse_retriever=FakeNurseRepo([nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[day1, day2],
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
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(min_rest_period=10),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments

    assert 1 in assignments.get(ShiftKey(1, 1), []), "Day 1 should be assigned"
    assert 1 in assignments.get(ShiftKey(1, 2), []), (
        "Day 2 should be assigned (16h gap > 10h min_rest, day-to-day uses standard rest)"
    )
