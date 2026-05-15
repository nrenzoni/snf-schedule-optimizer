"""II.4: Per-unit minimum staffing mandate tests."""

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
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    UnitMinimumStaffingConstraintStrategy,
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


async def test_per_unit_minimum_enforced() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn_emp = Employee(
        employee_id=1,
        name="Unit A RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
        primary_unit_id=1,
    )
    rn_comp = StaffCompensationRecord(
        employee_id=1,
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

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            UnitMinimumStaffingConstraintStrategy(),
        ],
        facility_rule_strategies=[],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn_emp]),
        nurse_retriever=FakeNurseRepo([rn_nurse]),
        hprd_calculator=FakeHprdRequirementCalculator({}),
        staff_compensation_service=FakeStaffCompensationRepo([rn_comp]),
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
                ),
                unit_minimums={
                    1: {HprdEnforcedRole.RN: 1.0},
                },
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
    assert 1 in assignments.get(ShiftKey(1, 1), [])


async def test_infeasible_when_unit_has_no_eligible_nurse() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    cna_emp = Employee(
        employee_id=2,
        name="CNA Only",
        job_title="CNA",
        hire_date=whenever.Date(2024, 1, 1),
    )
    cna_nurse = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
        primary_unit_id=1,
    )
    cna_comp = StaffCompensationRecord(
        employee_id=2,
        base_rate_effective=20.0,
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

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            UnitMinimumStaffingConstraintStrategy(),
        ],
        facility_rule_strategies=[],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([cna_emp]),
        nurse_retriever=FakeNurseRepo([cna_nurse]),
        hprd_calculator=FakeHprdRequirementCalculator({}),
        staff_compensation_service=FakeStaffCompensationRepo([cna_comp]),
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
                ),
                unit_minimums={
                    1: {HprdEnforcedRole.RN: 1.0},
                },
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider, preference_weights=PreferenceWeights()
    )

    assert not result.success, (
        "Should be infeasible when unit requires RN but only CNA available"
    )
    assert result.infeasibility_reason is not None
    details = result.infeasibility_reason.details
    assert details is not None
    assert "UnitMin" in details or "unit" in details.lower()


async def test_unit_minimum_overrides_facility_hprd() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn_emp = Employee(
        employee_id=1,
        name="Unit A RN",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
    )
    rn_nurse = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["RN"],
        shift_custom_preferences=[],
        primary_unit_id=1,
    )
    rn_comp = StaffCompensationRecord(
        employee_id=1,
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

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            UnitMinimumStaffingConstraintStrategy(),
        ],
        facility_rule_strategies=[],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn_emp]),
        nurse_retriever=FakeNurseRepo([rn_nurse]),
        hprd_calculator=FakeHprdRequirementCalculator({}),
        staff_compensation_service=FakeStaffCompensationRepo([rn_comp]),
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
                ),
                unit_minimums={
                    1: {HprdEnforcedRole.RN: 1.0},
                },
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
    assert 1 in assignments.get(ShiftKey(1, 1), [])
