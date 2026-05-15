"""III.3: PTO & Callout Buffer enhancement tests."""

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    MinMandates,
    MlModelOutputs,
    NurseProfile,
    OptimizationSettings,
    PTORequest,
    PreferenceWeights,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.engine import NurseShiftScheduleOptimizer
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    HprdStaffingConstraintStrategy,
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
    ShiftRequirementsRepoImpl,
)
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory

tz_ny = "America/New_York"


async def test_pto_full_day_blocks_assignment() -> None:
    """Employee has PTO on Jan 2; shift on Jan 2; verify nurse NOT assigned (infeasible)."""
    ref = whenever.ZonedDateTime(2025, 1, 2, 7, tz=tz_ny)

    emp = Employee(
        employee_id=1, name="PTO RN", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )
    nurse = NurseProfile(
        employee_id=1, available_hours_weekly=40, skills=["RN"], shift_custom_preferences=[]
    )
    comp = StaffCompensationRecord(
        employee_id=1, base_rate_effective=30.0, ot_multiplier=1.5,
        is_agency=False, effective_start_date=whenever.Date(2024, 1, 1),
    )

    shift = Shift(
        org_id=1, shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1, day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None, is_scheduled=True,
    )

    pto = PTORequest(
        employee_id=1,
        date=ref.date(),
        hours=0,
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
        facility_rule_strategies=[],
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
                facility_id=1, shifts=[shift],
                config=FacilityConfig(
                    org_id=1, facility_id=1, shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0, night_shift_multiplier=1.0, tz=tz_ny,
                ),
                pto_requests=[pto],
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider, preference_weights=PreferenceWeights(),
    )

    assert not result.success, "Should be infeasible with only PTO-blocked nurse"


async def test_callout_buffer_inflates_staffing() -> None:
    """use_callout_buffer=True, callout_forecast=0.10; HPRD RN target=1.0 -> effective ~1.1 -> ceil=2.
    Verify 2 RNs assigned."""
    ref = whenever.ZonedDateTime(2025, 1, 1, 7, tz=tz_ny)

    emp1 = Employee(
        employee_id=1, name="RN 1", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )
    emp2 = Employee(
        employee_id=2, name="RN 2", job_title="RN", hire_date=whenever.Date(2024, 1, 1)
    )
    nurse1 = NurseProfile(
        employee_id=1, available_hours_weekly=40, skills=["RN"], shift_custom_preferences=[]
    )
    nurse2 = NurseProfile(
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

    shift = Shift(
        org_id=1, shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1, day_shift=True,
        day_of_week=ref.date().day_of_week(),
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=8),
        unit_id=None, is_scheduled=True,
    )

    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={(1, HprdEnforcedRole.RN): 1.375}
    )

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
        facility_rule_strategies=[],
        penalty_strategies=[],
    )

    settings = OptimizationSettings(use_callout_buffer=True)

    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo([emp1, emp2]),
        nurse_retriever=FakeNurseRepo([nurse1, nurse2]),
        hprd_calculator=fake_hprd,
        staff_compensation_service=FakeStaffCompensationRepo([comp, comp2]),
        ml_model_retriever=FakeMLModelRepo(
            MlModelOutputs(
                turnover_risk_scores={},
                shift_call_out_forecast=0.10,
                unit_acuity_stress={},
                team_compatibility_scores={},
            )
        ),
        work_history_service=FakeWorkHistoryService({}),
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
                ),
                min_mandates=MinMandates(
                    min_rn_hprd=0.5,
                    min_lpn_hprd=0.0,
                    min_cna_hprd=2.4,
                    min_total_hprd=3.5,
                    min_staff_per_shift_rn=0,
                    min_staff_per_shift_lpn=0,
                    min_staff_per_shift_cna=0,
                ),
                optimization_settings=settings,
            )
        },
        pay_period_start=ref.subtract(hours=40).to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=settings,
    )

    result = await optimizer.solve(
        data_provider=provider, preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments
    staff = assignments.get(ShiftKey(1, 1), [])

    assert 1 in staff, "RN 1 should be assigned"
    assert 2 in staff, "RN 2 should be assigned (callout buffer inflates demand)"
    assert len(staff) >= 2, f"Expected 2 RNs assigned due to callout buffer, got {len(staff)}"
