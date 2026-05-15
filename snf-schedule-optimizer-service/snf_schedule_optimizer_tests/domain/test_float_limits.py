"""II.7: Float limit constraint tests."""

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    FacilityHrConfig,
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
    FloatLimitConstraintStrategy,
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


async def test_float_limit_not_exceeded() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn1_emp = Employee(
        employee_id=1,
        name="Float RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn1_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
        primary_unit_id=1,
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
        name="Home Unit RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn2_nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
        primary_unit_id=2,
    )
    rn2_comp = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=30.0,
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
                unit_id=2,
                is_scheduled=True,
            )
        )

    fake_hprd = FakeHprdRequirementCalculator(
        {(s.shift_id, HprdEnforcedRole.RN): 1.0 for s in shifts}
    )

    hr_config = FacilityHrConfig(
        max_weekly_hours_per_nurse=40,
        min_rest_hours_between_shifts=10.0,
        max_consecutive_work_days=5,
        max_total_hours_per_pay_period=80,
        max_patient_to_staff_ratio=None,
        mandatory_days_off_after_max_consecutive_days=None,
        max_weekend_shifts_per_month=None,
        max_floating_assignments_per_month=2,
        max_night_shifts_per_month=None,
        require_annual_training=None,
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            FloatLimitConstraintStrategy(),
        ],
        penalty_strategies=[],
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
                hr_config=hr_config,
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
    float_nurse_assignments = sum(1 for key, emps in assignments.items() if 1 in emps)
    assert float_nurse_assignments <= 2, (
        f"Float limit of 2 exceeded, got {float_nurse_assignments} floating assignments"
    )


async def test_no_float_limit_when_disabled() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn1_emp = Employee(
        employee_id=1,
        name="Unlimited Float RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn1_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
        primary_unit_id=1,
    )
    rn1_comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
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
                unit_id=2,
                is_scheduled=True,
            )
        )

    fake_hprd = FakeHprdRequirementCalculator(
        {(s.shift_id, HprdEnforcedRole.RN): 1.0 for s in shifts}
    )

    hr_config = FacilityHrConfig(
        max_weekly_hours_per_nurse=40,
        min_rest_hours_between_shifts=10.0,
        max_consecutive_work_days=5,
        max_total_hours_per_pay_period=80,
        max_patient_to_staff_ratio=None,
        mandatory_days_off_after_max_consecutive_days=None,
        max_weekend_shifts_per_month=None,
        max_floating_assignments_per_month=None,
        max_night_shifts_per_month=None,
        require_annual_training=None,
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            FloatLimitConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn1_emp]),
        nurse_retriever=FakeNurseRepo([rn1_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([rn1_comp]),
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
                hr_config=hr_config,
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
    float_nurse_assignments = sum(1 for key, emps in assignments.items() if 1 in emps)
    assert float_nurse_assignments == 3, (
        f"Without float limit, all 3 floating shifts should be assignable, got {float_nurse_assignments}"
    )
