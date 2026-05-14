from typing import cast

import pulp
import pytest
import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    LockedAssignment,
    MinMandates,
    MlModelOutputs,
    NurseProfile,
    OptimizationFailureCode,
    OptimizationRunStage,
    OptimizationRunStatus,
    OptimizationSettings,
    PreferenceWeights,
    ResidentAcuity,
    Shift,
    ShiftKey,
    ShiftSpecificRequirements,
    SolverTerminationReason,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.calculators import HprdRequirementCalculator
from snf_schedule_optimizer.optimizer.context import (
    FacilityScenarioContext,
    LpNurseShiftVariableHolder,
)
from snf_schedule_optimizer.optimizer.interfaces import IScenarioDataProvider
from snf_schedule_optimizer.optimizer.providers import ScenarioDataProviderFactory
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    MaxWeeklyHoursConstraintStrategy,
)
from snf_schedule_optimizer.optimizer.strategies.fixing import (
    LockedAssignmentConstraintStrategy,
)
from snf_schedule_optimizer.persistence.fakes import (
    FakeEmployeeRepo,
    FakeHprdRequirementCalculator,
    FakeMLModelRepo,
    FakeShiftRequirementsRepo,
    FakeStaffCompensationRepo,
    FakeWorkHistoryService,
)
from snf_schedule_optimizer.persistence.nurse_repo import INurseRepo
from snf_schedule_optimizer.resident_acuity_repo import FakeResidentAcuityPerShiftRepo
from snf_schedule_optimizer.solver import SolverResult

from .test_builder import OptimizerTestBuilder


class _LockedAssignmentProvider:
    def __init__(self, shifts: list[Shift]) -> None:
        self.shifts = shifts

    def get_shifts_for_facility(self, facility_id: int) -> list[Shift]:
        return [shift for shift in self.shifts if shift.facility_id == facility_id]


class _ShiftScopedNurseRepo(INurseRepo):
    def __init__(self, nurses_by_shift: dict[ShiftKey, list[NurseProfile]]) -> None:
        self.nurses_by_shift = nurses_by_shift

    async def get_nurses(self, shift: Shift) -> list[NurseProfile]:
        return self.nurses_by_shift.get(shift.shift_key, [])

    async def get_nurse(self, employee_id: int) -> NurseProfile | None:
        for nurses in self.nurses_by_shift.values():
            for nurse in nurses:
                if nurse.employee_id == employee_id:
                    return nurse
        return None

    async def save_nurse_profile(self, org_id: int, nurse: NurseProfile) -> None:
        pass


def test_run_contract_enums_serialize_to_expected_values() -> None:
    assert OptimizationRunStatus.QUEUED.value == "queued"
    assert OptimizationRunStage.SOLVING.value == "solving"
    assert OptimizationFailureCode.SOLVER_TIMEOUT.value == "solver_timeout"
    assert SolverTerminationReason.OPTIMAL.value == "optimal"


def test_solver_result_contract_holds_structured_termination() -> None:
    result = SolverResult(
        termination_reason=SolverTerminationReason.OPTIMAL,
        status_code=pulp.LpStatusOptimal,
        status_label="Optimal",
        objective_value=12.5,
        elapsed_ms=7.0,
    )

    assert result.termination_reason is SolverTerminationReason.OPTIMAL
    assert result.objective_value == 12.5


async def test_demand_model_filters_census_by_unit_and_uses_modifiers_not_headcount() -> None:
    shift_start = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=101),
        shift_number=1,
        day_shift=True,
        day_of_week=shift_start.date().day_of_week(),
        shift_start_dt=shift_start,
        shift_end_dt=shift_start.add(hours=8),
        unit_id=10,
        is_scheduled=True,
    )
    acuity = [
        ResidentAcuity(
            resident_id=1,
            unit_id=10,
            census_day=shift_start.start_of_day(),
            pt_score_gg=14,
            nta_score=1,
            clinical_category="high",
        ),
        ResidentAcuity(
            resident_id=2,
            unit_id=10,
            census_day=shift_start.start_of_day(),
            pt_score_gg=4,
            nta_score=1,
            clinical_category="base",
        ),
        ResidentAcuity(
            resident_id=3,
            unit_id=20,
            census_day=shift_start.start_of_day(),
            pt_score_gg=14,
            nta_score=8,
            clinical_category="other-unit",
        ),
    ]
    calculator = HprdRequirementCalculator(
        resident_acuity_retriever=FakeResidentAcuityPerShiftRepo(acuity),
        shift_requirements_retriever=FakeShiftRequirementsRepo(
            default_requirements=ShiftSpecificRequirements(
                target_hprd_rn=4.0,
                target_hprd_lpn=2.0,
                target_hprd_cna=8.0,
                target_total_hprd=12.0,
            )
        ),
    )
    context = FacilityScenarioContext(
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
            tz="America/New_York",
        ),
        min_mandates=MinMandates(
            min_rn_hprd=0.0,
            min_lpn_hprd=0.0,
            min_cna_hprd=0.0,
            min_total_hprd=0.0,
            min_staff_per_shift_rn=0,
            min_staff_per_shift_lpn=0,
            min_staff_per_shift_cna=0,
        ),
        optimization_settings=OptimizationSettings(
            use_ml_forecast=True,
            use_callout_buffer=True,
            buffer_threshold=10,
        ),
    )

    requirements = await calculator.calculate_requirements(context)

    assert requirements[101, HprdEnforcedRole.RN] == pytest.approx(1.6)
    assert requirements[101, HprdEnforcedRole.LPN] == pytest.approx(0.8)
    assert requirements[101, HprdEnforcedRole.CNA] == pytest.approx(3.2)
    assert requirements.get_total_req(101) == pytest.approx(4.8)


async def test_locked_assignment_strategy_only_forces_selected_assignment() -> None:
    shift_start = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=101),
        shift_number=1,
        day_shift=True,
        day_of_week=shift_start.date().day_of_week(),
        shift_start_dt=shift_start,
        shift_end_dt=shift_start.add(hours=8),
        unit_id=10,
        is_scheduled=True,
    )
    lp_holder = LpNurseShiftVariableHolder()
    locked_var = lp_holder.add_variable(shift, 1)
    open_var = lp_holder.add_variable(shift, 2)
    problem = pulp.LpProblem("lock-test", pulp.LpMinimize)

    strategy = LockedAssignmentConstraintStrategy(
        [LockedAssignment(employee_id=1, shift_key=shift.shift_key)]
    )
    await strategy.apply_constraints(
        problem,
        lp_holder,
        cast(IScenarioDataProvider, _LockedAssignmentProvider([shift])),
        facility_id=1,
    )

    constraints = list(problem.constraints.values())
    assert len(constraints) == 1
    assert constraints[0].get(locked_var, None) == 1
    assert constraints[0].get(open_var, None) is None


async def test_history_hours_limit_weekly_capacity_as_hard_constraint() -> None:
    ref_date = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift_1 = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=201),
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date,
        shift_end_dt=ref_date.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    shift_2 = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=202),
        shift_number=2,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date.add(hours=24),
        shift_end_dt=ref_date.add(hours=32),
        unit_id=None,
        is_scheduled=True,
    )
    cheap = Employee(
        employee_id=1,
        name="Cheap",
        job_title="CNA",
        hire_date=ref_date.date(),
    )
    backup = Employee(
        employee_id=2,
        name="Backup",
        job_title="CNA",
        hire_date=ref_date.date(),
    )
    cheap_profile = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )
    backup_profile = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )
    builder = (
        OptimizerTestBuilder()
        .with_employees([cheap, backup], [cheap_profile, backup_profile])
        .with_financials(
            [
                StaffCompensationRecord(
                    employee_id=1,
                    base_rate_effective=10.0,
                    effective_start_date=ref_date.date(),
                    ot_multiplier=1.5,
                    is_agency=False,
                ),
                StaffCompensationRecord(
                    employee_id=2,
                    base_rate_effective=20.0,
                    effective_start_date=ref_date.date(),
                    ot_multiplier=1.5,
                    is_agency=False,
                ),
            ]
        )
        .with_history({1: 32.0})
        .with_hprd_calculator(
            FakeHprdRequirementCalculator(
                requirements_map={
                    (201, HprdEnforcedRole.CNA): 1.0,
                    (202, HprdEnforcedRole.CNA): 1.0,
                }
            )
        )
        .with_strategies(constraints=[MaxWeeklyHoursConstraintStrategy()])
    )
    optimizer = builder.build_optimizer()
    context = FacilityScenarioContext(
        facility_id=1,
        shifts=[shift_1, shift_2],
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
            tz="America/New_York",
        ),
        min_mandates=None,
    )
    provider = builder.factory.create(
        org_id=1,
        facility_contexts={1: context},
        pay_period_start=ref_date.start_of_day().to_instant(),
        optimization_start_time=ref_date.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(provider, PreferenceWeights())

    assert result.success
    assert result.optimal_schedule is not None
    cheap_assignments = sum(
        1
        for employee_ids in result.optimal_schedule.shift_assignments.values()
        if 1 in employee_ids
    )
    assert cheap_assignments == 1


async def test_candidate_cache_is_isolated_by_shift_key() -> None:
    ref_date = whenever.ZonedDateTime(2025, 1, 1, 7, tz="America/New_York")
    shift_a = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=301),
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date,
        shift_end_dt=ref_date.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    shift_b = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=2, shift_id=301),
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date,
        shift_end_dt=ref_date.add(hours=8),
        unit_id=None,
        is_scheduled=True,
    )
    nurse_a = NurseProfile(
        employee_id=1,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )
    nurse_b = NurseProfile(
        employee_id=2,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )
    provider = ScenarioDataProviderFactory(
        employee_retriever=FakeEmployeeRepo(
            [
                Employee(1, "Facility A", "CNA", ref_date.date()),
                Employee(2, "Facility B", "CNA", ref_date.date()),
            ]
        ),
        nurse_retriever=_ShiftScopedNurseRepo(
            {shift_a.shift_key: [nurse_a], shift_b.shift_key: [nurse_b]}
        ),
        hprd_calculator=FakeHprdRequirementCalculator(),
        staff_compensation_service=FakeStaffCompensationRepo([]),
        ml_model_retriever=FakeMLModelRepo(
            MlModelOutputs(
                turnover_risk_scores={},
                shift_call_out_forecast=0.0,
                unit_acuity_stress={},
                team_compatibility_scores={},
            )
        ),
        work_history_service=FakeWorkHistoryService({}),
    ).create(
        org_id=1,
        facility_contexts={
            1: FacilityScenarioContext(
                facility_id=1,
                shifts=[shift_a],
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
                    tz="America/New_York",
                ),
            ),
            2: FacilityScenarioContext(
                facility_id=2,
                shifts=[shift_b],
                config=FacilityConfig(
                    org_id=1,
                    facility_id=2,
                    shifts_per_day=3,
                    overtime_threshold_hours_per_week=40,
                    start_of_work_week_day=whenever.Weekday.MONDAY,
                    start_of_work_day_time=whenever.Time(7, 0, 0),
                    pay_period=whenever.DateDelta(weeks=1),
                    weekend_multiplier=1.0,
                    night_shift_multiplier=1.0,
                    tz="America/New_York",
                ),
            ),
        },
        pay_period_start=ref_date.start_of_day().to_instant(),
        optimization_start_time=ref_date.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    assert [n.employee_id for n in await provider.get_nurses_for_shift(shift_a)] == [1]
    assert [n.employee_id for n in await provider.get_nurses_for_shift(shift_b)] == [2]
