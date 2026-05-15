import pathlib
from unittest.mock import AsyncMock, MagicMock

import whenever

from snf_schedule_optimizer.domain.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.domain.payroll.calculations.shift_slicers import (
    TimeOverlapShiftSlicer,
)
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
from snf_schedule_optimizer.optimizer.strategies.pay import WeeklyVolumePayStrategy
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
from snf_schedule_optimizer.reporting.pbj_export import PbjReportGenerator

tz_ny = "America/New_York"


async def test_pbj_report_generates_correct_rows() -> None:
    ref = whenever.ZonedDateTime(2025, 1, 9, 7, tz=tz_ny)
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.THURSDAY,
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=12),
        unit_id=None,
        is_scheduled=True,
    )

    rn_emp = Employee(
        employee_id=1,
        name="RN A",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
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

    mock_eligibility = MagicMock()
    mock_eligibility.get_applicable_rules = AsyncMock(return_value=([], []))
    pay_processor = ShiftPayProcessor(
        eligibility_service=mock_eligibility,
        slicer=TimeOverlapShiftSlicer(),
        compensation_service=FakeStaffCompensationRepo([rn_comp]),
    )

    fake_hprd = FakeHprdRequirementCalculator({(1, HprdEnforcedRole.RN): 1.0})

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[
            WeeklyVolumePayStrategy(
                shift_pay_processor=pay_processor,
                threshold=40.0,
            ),
        ],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
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
                ),
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None

    generator = PbjReportGenerator()
    rows = await generator.generate_pbj_report(
        shift_assignments=result.optimal_schedule.shift_assignments,
        data_provider=provider,
        facility_id=1,
        reporting_period_start=whenever.Date(2025, 1, 1),
        reporting_period_end=whenever.Date(2025, 1, 31),
    )

    assert len(rows) == 1, f"Expected 1 PBJ row, got {len(rows)}"
    row = rows[0]
    assert row["STAFFING_HOURS"] == "Y"
    assert row["EMPLID"] == "1"
    assert row["JOB_TTL_CD"] == "RN"
    assert row["HRS_WORKED"] == 12.0
    assert row["FACILITY_ID"] == "1"
    assert row["PAY_TYPE"] == "REG"


async def test_pbj_csv_export_writes_file(tmp_path: pathlib.Path) -> None:
    ref = whenever.ZonedDateTime(2025, 1, 9, 7, tz=tz_ny)
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(facility_id=1, shift_id=1),
        shift_number=1,
        day_shift=True,
        day_of_week=whenever.Weekday.THURSDAY,
        shift_start_dt=ref,
        shift_end_dt=ref.add(hours=12),
        unit_id=None,
        is_scheduled=True,
    )

    rn_emp = Employee(
        employee_id=1,
        name="RN A",
        job_title="RN",
        hire_date=whenever.Date(2024, 1, 1),
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

    mock_eligibility = MagicMock()
    mock_eligibility.get_applicable_rules = AsyncMock(return_value=([], []))
    pay_processor = ShiftPayProcessor(
        eligibility_service=mock_eligibility,
        slicer=TimeOverlapShiftSlicer(),
        compensation_service=FakeStaffCompensationRepo([rn_comp]),
    )

    fake_hprd = FakeHprdRequirementCalculator({(1, HprdEnforcedRole.RN): 1.0})

    optimizer = NurseShiftScheduleOptimizer(
        core_variable_strategy=CoreVariableGenerationStrategy(),
        global_pay_strategies=[
            WeeklyVolumePayStrategy(
                shift_pay_processor=pay_processor,
                threshold=40.0,
            ),
        ],
        facility_constraint_strategies=[
            HprdStaffingConstraintStrategy(NurseHardBlockCheckerImpl()),
        ],
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
                ),
            )
        },
        pay_period_start=ref.to_instant(),
        optimization_start_time=ref.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=provider,
        preference_weights=PreferenceWeights(),
    )

    assert result.success, f"Infeasible: {result.infeasibility_reason}"
    assert result.optimal_schedule is not None

    generator = PbjReportGenerator()
    rows = await generator.generate_pbj_report(
        shift_assignments=result.optimal_schedule.shift_assignments,
        data_provider=provider,
        facility_id=1,
        reporting_period_start=whenever.Date(2025, 1, 1),
        reporting_period_end=whenever.Date(2025, 1, 31),
    )

    csv_path = tmp_path / "pbj_report.csv"
    generator.generate_pbj_csv(rows, str(csv_path))

    assert csv_path.exists(), f"CSV file not created at {csv_path}"
    content = csv_path.read_text()
    lines = content.strip().split("\n")
    assert len(lines) >= 2, f"Expected header + at least 1 row, got {len(lines)} lines"
    assert "STAFFING_HOURS" in lines[0]
    assert "EMPLID" in lines[0]
    assert "WORK_DATE" in lines[0]
