"""II.5: FT/PT/PRN employee classification tests."""

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    EmploymentClassification,
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
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    EmploymentClassificationConstraintStrategy,
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


async def test_full_time_capped_at_40h() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn_emp = Employee(
        employee_id=1,
        name="FT RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
        classification=EmploymentClassification.FULL_TIME,
    )
    rn_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    rn_comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    shifts = []
    for i in range(6):
        shift_start = ref.add(days=i)
        shifts.append(
            Shift(
                org_id=1,
                shift_key=ShiftKey(facility_id=1, shift_id=i + 1),
                shift_number=1,
                day_shift=True,
                day_of_week=shift_start.date().day_of_week(),
                shift_start_dt=shift_start,
                shift_end_dt=shift_start.add(hours=8),
                unit_id=None,
                is_scheduled=True,
            )
        )

    fake_hprd = FakeHprdRequirementCalculator(
        {(s.shift_id, HprdEnforcedRole.RN): 1.0 for s in shifts}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[],
        facility_rule_strategies=[
            EmploymentClassificationConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn_emp]),
        nurse_retriever=FakeNurseRepo([rn_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([rn_comp]),
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
        data_provider=provider, preference_weights=PreferenceWeights()
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments
    assigned_count = sum(1 for key, emps in assignments.items() if 1 in emps)
    assert assigned_count <= 5, (
        f"FT nurse capped at 40h (5x8h), got {assigned_count} shifts"
    )


async def test_part_time_capped_at_fraction() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    pt_emp = Employee(
        employee_id=2,
        name="PT RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
        classification=EmploymentClassification.PART_TIME,
    )
    pt_nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    pt_comp = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=28.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    shifts = []
    for i in range(5):
        shift_start = ref.add(days=i)
        shifts.append(
            Shift(
                org_id=1,
                shift_key=ShiftKey(facility_id=1, shift_id=i + 1),
                shift_number=1,
                day_shift=True,
                day_of_week=shift_start.date().day_of_week(),
                shift_start_dt=shift_start,
                shift_end_dt=shift_start.add(hours=8),
                unit_id=None,
                is_scheduled=True,
            )
        )

    fake_hprd = FakeHprdRequirementCalculator(
        {(s.shift_id, HprdEnforcedRole.RN): 1.0 for s in shifts}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[],
        facility_rule_strategies=[
            EmploymentClassificationConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([pt_emp]),
        nurse_retriever=FakeNurseRepo([pt_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([pt_comp]),
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
                    part_time_hour_fraction=0.75,
                ),
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider, preference_weights=PreferenceWeights()
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments
    assigned_count = sum(1 for key, emps in assignments.items() if 2 in emps)
    assert assigned_count <= 3, (
        f"PT nurse capped at 30h (40*0.75, 3x8h), got {assigned_count} shifts"
    )


async def test_prn_no_minimum_guarantee() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    prn_emp = Employee(
        employee_id=3,
        name="PRN RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
        classification=EmploymentClassification.PRN,
    )
    prn_nurse = NurseProfile(
        employee_id=3,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    prn_comp = StaffCompensationRecord(
        employee_id=3,
        base_rate_effective=35.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )

    shifts = []
    for i in range(3):
        shift_start = ref.add(days=i)
        shifts.append(
            Shift(
                org_id=1,
                shift_key=ShiftKey(facility_id=1, shift_id=i + 1),
                shift_number=1,
                day_shift=True,
                day_of_week=shift_start.date().day_of_week(),
                shift_start_dt=shift_start,
                shift_end_dt=shift_start.add(hours=8),
                unit_id=None,
                is_scheduled=True,
            )
        )

    fake_hprd = FakeHprdRequirementCalculator(
        {(s.shift_id, HprdEnforcedRole.RN): 0.0 for s in shifts}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[],
        facility_rule_strategies=[
            EmploymentClassificationConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([prn_emp]),
        nurse_retriever=FakeNurseRepo([prn_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([prn_comp]),
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
        data_provider=provider, preference_weights=PreferenceWeights()
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
