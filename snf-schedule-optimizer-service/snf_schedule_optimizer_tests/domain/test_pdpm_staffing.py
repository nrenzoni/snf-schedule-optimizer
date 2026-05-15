"""II.6: PDPM category staffing ratio tests."""

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
    PdpmCategoryConstraintStrategy,
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


def _make_employee_comp(
    eid: int, name: str, role: str, rate: float
) -> tuple[Employee, NurseProfile, StaffCompensationRecord]:
    emp = Employee(
        employee_id=eid,
        name=name,
        job_title=role,
        hire_date=whenever.Date(2024, 1, 1),
    )
    nurse = NurseProfile(
        employee_id=eid,
        available_hours_weekly=40,
        skills=[role],
        shift_custom_preferences=[],
    )
    comp = StaffCompensationRecord(
        employee_id=eid,
        base_rate_effective=rate,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=whenever.Date(2024, 1, 1),
    )
    return emp, nurse, comp


async def test_pdpm_category_drives_nurse_count() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn_emp, rn_nurse, rn_comp = _make_employee_comp(1, "RN1", "RN", 30.0)
    rn_emp2, rn_nurse2, rn_comp2 = _make_employee_comp(2, "RN2", "RN", 30.0)

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

    fake_hprd = FakeHprdRequirementCalculator({})

    strategy = PdpmCategoryConstraintStrategy()

    category_counts: dict[str, int] = {"Extensive Services": 20}
    strategy._compute_pdpm_category_counts = lambda dp, fid: category_counts  # type: ignore[assignment]

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[strategy],
        facility_rule_strategies=[],
        penalty_strategies=[],
    )

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([rn_emp, rn_emp2]),
        nurse_retriever=FakeNurseRepo([rn_nurse, rn_nurse2]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([rn_comp, rn_comp2]),
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
                    pdpm_category_ratios={
                        "Extensive Services": {
                            HprdEnforcedRole.RN: 0.083,
                        },
                    },
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
    assigned = assignments.get(ShiftKey(1, 1), [])
    assert len(assigned) >= 2, (
        f"PDPM Extensive Services 20*0.083=1.66 => 2 RNs required, got {len(assigned)}"
    )


async def test_pdpm_no_category_no_extra_staff() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    rn_emp, rn_nurse, rn_comp = _make_employee_comp(1, "RN1", "RN", 30.0)

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

    strategy = PdpmCategoryConstraintStrategy()

    category_counts: dict[str, int] = {}
    strategy._compute_pdpm_category_counts = lambda dp, fid: category_counts  # type: ignore[assignment]

    fake_hprd = FakeHprdRequirementCalculator({})

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[strategy],
        facility_rule_strategies=[],
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
                    pdpm_category_ratios={},
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
