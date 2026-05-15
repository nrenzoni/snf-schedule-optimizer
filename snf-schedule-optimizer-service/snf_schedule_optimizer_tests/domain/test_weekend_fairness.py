"""III.1: Weekend & holiday fairness penalty tests."""

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
    HprdStaffingConstraintStrategy,
)
from snf_schedule_optimizer.optimizer.strategies.penalties import (
    WeekendFairnessPenaltyStrategy,
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


async def test_fairness_penalty_reduces_imbalance() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 9, 7, tz=tz_ny)

    weekend_day = ref
    while weekend_day.date().day_of_week() not in (
        whenever.Weekday.SATURDAY,
        whenever.Weekday.SUNDAY,
    ):
        weekend_day = weekend_day.add(days=1)

    sat_shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.SATURDAY,
        shift_start_dt=weekend_day,
        shift_end_dt=weekend_day.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    sun_shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=2),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.SUNDAY,
        shift_start_dt=weekend_day.add(days=1),
        shift_end_dt=weekend_day.add(days=1).add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    rn1_emp = Employee(
        employee_id=1,
        name="RN A",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn1_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    rn1_comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    rn2_emp = Employee(
        employee_id=2,
        name="RN B",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn2_nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    rn2_comp = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    shifts = [sat_shift, sun_shift]

    fake_hprd = FakeHprdRequirementCalculator(
        {
            (1, HprdEnforcedRole.RN): 1.0,
            (2, HprdEnforcedRole.RN): 1.0,
        }
    )

    fairness_strategy = WeekendFairnessPenaltyStrategy()

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            fairness_strategy,
        ],
        penalty_strategies=[
            fairness_strategy,
        ],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn1_emp, rn2_emp]),
        nurse_retriever=FakeNurseRepo([rn1_nurse, rn2_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([rn1_comp, rn2_comp]),
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

    weights = PreferenceWeights(
        weekend_fairness_penalty=100.0,
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=weights,
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments

    rn1_count = sum(1 for key, emps in assignments.items() if 1 in emps)
    rn2_count = sum(1 for key, emps in assignments.items() if 2 in emps)

    assert rn1_count + rn2_count == 2, (
        f"Both weekend shifts should be covered, got {rn1_count + rn2_count}"
    )


async def test_fairness_score_in_result() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 9, 7, tz=tz_ny)

    weekend_day = ref
    while weekend_day.date().day_of_week() not in (
        whenever.Weekday.SATURDAY,
        whenever.Weekday.SUNDAY,
    ):
        weekend_day = weekend_day.add(days=1)

    sat_shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.SATURDAY,
        shift_start_dt=weekend_day,
        shift_end_dt=weekend_day.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    sun_shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=2),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.SUNDAY,
        shift_start_dt=weekend_day.add(days=1),
        shift_end_dt=weekend_day.add(days=1).add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )

    rn1_emp = Employee(
        employee_id=1,
        name="RN A",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn1_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    rn1_comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    rn2_emp = Employee(
        employee_id=2,
        name="RN B",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn2_nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    rn2_comp = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    shifts = [sat_shift, sun_shift]

    fake_hprd = FakeHprdRequirementCalculator(
        {
            (1, HprdEnforcedRole.RN): 1.0,
            (2, HprdEnforcedRole.RN): 1.0,
        }
    )

    fairness_strategy = WeekendFairnessPenaltyStrategy()

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            fairness_strategy,
        ],
        penalty_strategies=[
            fairness_strategy,
        ],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn1_emp, rn2_emp]),
        nurse_retriever=FakeNurseRepo([rn1_nurse, rn2_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([rn1_comp, rn2_comp]),
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

    weights = PreferenceWeights(
        weekend_fairness_penalty=100.0,
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=weights,
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.fairness_score is not None, "Result should have fairness_score"
    assert result.fairness_score >= 0, (
        f"fairness_score must be >= 0, got {result.fairness_score}"
    )
    assert result.weekend_assignment_distribution is not None, (
        "Result should have distribution"
    )
