"""III.4: Preceptor / Charge Nurse ratio constraint tests."""

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
from snf_schedule_optimizer.optimizer.calculators import NurseHardBlockCheckerImpl
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    HprdStaffingConstraintStrategy,
    PreceptorRatioConstraintStrategy,
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


async def test_preceptor_required_for_new_grads() -> None:
    """2 new grads (PRNs), 0 preceptors on shift; verify infeasible or preceptor assigned."""
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    new_grad1 = Employee(
        employee_id=1,
        name="New Grad 1",
        job_title="RN",
        hire_date=whenever.Date(2024, 12, 20),
        classification=EmploymentClassification.PRN,
    )
    new_grad2 = Employee(
        employee_id=2,
        name="New Grad 2",
        job_title="RN",
        hire_date=whenever.Date(2024, 12, 25),
        classification=EmploymentClassification.PRN,
    )
    preceptor_emp = Employee(
        employee_id=3,
        name="Preceptor RN",
        job_title="RN",
        hire_date=whenever.Date(2020, 1, 1),
        classification=EmploymentClassification.FULL_TIME,
    )

    ng_nurse1 = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    ng_nurse2 = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    preceptor_nurse = NurseProfile(
        employee_id=3,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
        is_preceptor=True,
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
    comp3 = StaffCompensationRecord(
        employee_id=3,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2020, 1, 1),
    )

    shift = Shift(
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

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={(1, HprdEnforcedRole.RN): 3.0}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            PreceptorRatioConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([new_grad1, new_grad2, preceptor_emp]),
        nurse_retriever=FakeNurseRepo([ng_nurse1, ng_nurse2, preceptor_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp, comp2, comp3]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift],
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
                    max_new_grads_per_preceptor=2,
                ),
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments
    staff = assignments.get(ShiftKey(1, 1), [])

    assert 3 in staff, "Preceptor should be assigned to cover new grads"
    assert len(staff) >= 3, (
        f"Expected preceptor + at least some new grads, got {len(staff)}"
    )


async def test_preceptor_infeasible_without_preceptor() -> None:
    """2 new grads, 0 preceptors available; verify infeasible."""
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    new_grad1 = Employee(
        employee_id=1,
        name="New Grad 1",
        job_title="RN",
        hire_date=whenever.Date(2024, 12, 20),
        classification=EmploymentClassification.PRN,
    )
    new_grad2 = Employee(
        employee_id=2,
        name="New Grad 2",
        job_title="RN",
        hire_date=whenever.Date(2024, 12, 25),
        classification=EmploymentClassification.PRN,
    )

    ng_nurse1 = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
    )
    ng_nurse2 = NurseProfile(
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

    shift = Shift(
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

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={(1, HprdEnforcedRole.RN): 1.0}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            PreceptorRatioConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([new_grad1, new_grad2]),
        nurse_retriever=FakeNurseRepo([ng_nurse1, ng_nurse2]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp, comp2]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift],
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
                    max_new_grads_per_preceptor=2,
                ),
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert not result.success, "Should be infeasible: new grads with no preceptor"


async def test_charge_nurse_required_per_shift() -> None:
    """require_charge_nurse_per_shift=True, no charge nurse available; verify infeasible."""
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn_emp = Employee(
        employee_id=1,
        name="Regular RN",
        job_title="RN",
        hire_date=whenever.Date(2023, 1, 1),
        classification=EmploymentClassification.FULL_TIME,
    )

    rn_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
        is_charge_nurse=False,
    )

    comp = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2023, 1, 1),
    )

    shift = Shift(
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

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={(1, HprdEnforcedRole.RN): 1.0}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[
            PreceptorRatioConstraintStrategy(),
        ],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn_emp]),
        nurse_retriever=FakeNurseRepo([rn_nurse]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp]),
        ml_model_retriever=FakeMLModelRepo(MlModelOutputs({}, 0.0, {}, {})),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift],
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
                    require_charge_nurse_per_shift=True,
                ),
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert not result.success, "Should be infeasible: no charge nurse when required"
