from __future__ import annotations

import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    MinMandates,
    NurseProfile,
    OptimizationSettings,
    PreferenceType,
    PreferenceWeights,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
    StaffShiftPreference,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.persistence.fakes import (
    FakeHprdRequirementCalculator,
)
from snf_schedule_optimizer.utils.time_utils import TimeRoundingUtility

from .support import OptimizerTestBuilder

tz_ny = "America/New_York"


async def test_financial_hero_ot_vs_agency() -> None:
    """
    Demonstrates ROI: Solver chooses internal OT over expensive Agency
    even when the internal nurse is about to hit the weekly cap.
    """
    # 1. Setup Dates
    ref_date = whenever.ZonedDateTime(2025, 11, 10, tz=tz_ny)

    # 2. Setup 12-Hour Shift
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(
            facility_id=1,
            shift_id=1,
        ),
        shift_start_dt=ref_date.add(hours=7),
        shift_end_dt=ref_date.add(hours=19),  # 12 Hours
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        unit_id=None,
        is_scheduled=True,
    )

    # 3. Setup Employees
    # Nurse A: Staff, $30/hr. Worked 38 hours already.
    # Cost logic: 2 hrs @ $30 + 10 hrs @ $45 (1.5x) = $60 + $450 = $510
    nurse_a = Employee(
        employee_id=1,
        name="Alice Staff",
        hire_date=ref_date.subtract(years=1).date(),
        job_title="RN",
        # base_rate=30.0,
    )
    comp_a = StaffCompensationRecord(
        employee_id=1,
        base_rate_effective=30.0,
        ot_multiplier=1.5,
        effective_start_date=ref_date.subtract(years=1).date(),
        is_agency=False,
    )
    profile_a = NurseProfile(
        employee_id=1,
        available_hours_weekly=50,
        skills=["RN"],
        shift_custom_preferences=[],
    )

    # Nurse B: Agency, $55/hr flat.
    # Cost logic: 12 hrs @ $55 = $660
    nurse_b = Employee(
        employee_id=323,
        name="Bob Agency",
        hire_date=ref_date.subtract(months=1).date(),
        job_title="RN",
    )
    comp_b = StaffCompensationRecord(
        employee_id=323,
        base_rate_effective=55.0,
        ot_multiplier=1.0,  # Agency usually flat rate
        effective_start_date=ref_date.subtract(months=1).date(),
        is_agency=True,
    )
    profile_b = NurseProfile(
        employee_id=323,
        available_hours_weekly=12,
        skills=["RN"],
        shift_custom_preferences=[],
    )

    test_builder = (
        OptimizerTestBuilder()
        .with_employees([nurse_a, nurse_b], [profile_a, profile_b])
        .with_financials([comp_a, comp_b])
        .with_history({1: 38.0})  # Specific setup for this test
    )

    context = FacilityScenarioContext(
        facility_id=1,
        shifts=[shift],
        config=FacilityConfig(
            org_id=1,
            facility_id=1,
            overtime_threshold_hours_per_week=40,
            shifts_per_day=2,
            start_of_work_week_day=whenever.Weekday.MONDAY,
            start_of_work_day_time=whenever.Time(7, 0, 0),
            pay_period=whenever.DateDelta(weeks=1),
            weekend_multiplier=1.5,
            night_shift_multiplier=2.0,
            tz=tz_ny,
        ),
        min_mandates=MinMandates(
            min_rn_hprd=0.0,
            min_lpn_hprd=0,
            min_cna_hprd=0,
            min_total_hprd=0,
            min_staff_per_shift_rn=1,
            min_staff_per_shift_lpn=0,
            min_staff_per_shift_cna=0,
        ),
    )

    # side effect: creates factory
    optimizer = test_builder.build_optimizer()

    data_provider = test_builder.factory.create(
        org_id=1,
        facility_contexts={1: context},
        pay_period_start=TimeRoundingUtility.start_of_week_zoned(ref_date).to_instant(),
        optimization_start_time=ref_date.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    # 6. Solve
    result = await optimizer.solve(
        data_provider,
        preference_weights=PreferenceWeights(),
    )

    # 7. Assertion
    assert result.success is True
    assert result.optimal_schedule is not None
    assigned_ids = result.optimal_schedule.shift_assignments[shift.shift_key]

    print("\n--- TEST 1: FINANCIAL HERO ---")
    if 1 in assigned_ids:
        print("SUCCESS: Solver chose Staff (w/ OT) over Agency.")
        # Staff: 2hr @ 30 + 10hr @ 45 = 60 + 450 = 510
        # Agency: 12hr @ 55 = 660
        print(f"Estimated Savings: ${660 - 510}")
    elif 323 in assigned_ids:
        print("FAILURE: Solver chose Agency.")
    else:
        print("FAILURE: No assignment made.")

    assert 1 in assigned_ids


async def test_compliance_safety_net() -> None:
    """
    Demonstrates Safety: Solver violates a nurse's soft preference
    to prevent an HPRD violation (Hard/Heavy constraint).
    """
    # 1. Setup Dates
    ref_date = whenever.ZonedDateTime(2025, 11, 11, tz=tz_ny)

    # 2. Setup Shift
    shift = Shift(
        org_id=1,
        shift_key=ShiftKey(
            facility_id=1,
            shift_id=2,
        ),
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        shift_start_dt=ref_date.add(hours=7),
        shift_end_dt=ref_date.add(hours=15),  # 8 Hours
        unit_id=None,
        is_scheduled=True,
    )

    # 3. Setup Employees
    # Nurse A: The ONLY RN available. Wants off.
    nurse_a = Employee(
        employee_id=456,
        name="Sue RN",
        hire_date=ref_date.date(),
        job_title="RN",
    )
    # Note: StaffCompensationRecord arguments simplified for readability if defaults allow,
    # otherwise keep full arguments.
    comp_a = StaffCompensationRecord(
        employee_id=456,
        base_rate_effective=40.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=ref_date.date(),
        effective_end_date=None,
        union_contract_id=None,
    )
    profile_a = NurseProfile(
        employee_id=456,
        available_hours_weekly=40,
        skills=["RN"],
        # Note: The builder uses the penalty map below, effectively overriding this object
        # but we keep it here to make the test data semantically correct.
        shift_custom_preferences=[
            StaffShiftPreference(
                preference_type=PreferenceType.SPECIFIC_DAY_OFF,
                specific_value=str(ref_date.date().day_of_week()),
                penalty_weight=10,
                is_hard_block=False,
            ),
        ],
    )

    # Nurse B: A CNA (Cannot fill RN slot).
    nurse_b = Employee(
        employee_id=123,
        name="Bob CNA",
        hire_date=ref_date.date(),
        job_title="CNA",
    )
    comp_b = StaffCompensationRecord(
        employee_id=123,
        base_rate_effective=20.0,
        ot_multiplier=1.5,
        is_agency=False,
        effective_start_date=ref_date.date(),
        effective_end_date=None,
        union_contract_id=None,
    )
    profile_b = NurseProfile(
        employee_id=123,
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )

    # 4. Initialize Optimizer using Builder
    # Define the fake calculator to force the logic we want to test
    fake_hprd_calc = FakeHprdRequirementCalculator(
        requirements_map={
            (2, HprdEnforcedRole.RN): 1.0,
            (2, HprdEnforcedRole.CNA): 0.0,
        }
    )

    optimizer_builder = (
        OptimizerTestBuilder()
        .with_employees([nurse_a, nurse_b], [profile_a, profile_b])
        .with_financials([comp_a, comp_b])
        # This map tells the Fake Processor: "If you see RN_SUE on SHIFT_CRITICAL, return 50.0 penalty"
        .with_preference_penalties({"RN_SUE:SHIFT_CRITICAL": 50.0})
        .with_hprd_calculator(fake_hprd_calc)
    )

    # 5. Setup Context
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
            weekend_multiplier=1.5,
            night_shift_multiplier=2.0,
            tz=tz_ny,
        ),
        # Since we injected fake_hprd_calc, these specific numbers are actually ignored
        # but required for the context object validity.
        min_mandates=None,
    )

    optimizer = optimizer_builder.build_optimizer()

    data_provider = optimizer_builder.factory.create(
        org_id=1,
        facility_contexts={1: context},
        pay_period_start=TimeRoundingUtility.start_of_week_zoned(ref_date).to_instant(),
        optimization_start_time=ref_date.to_instant(),
        optimization_settings=OptimizationSettings(),
    )

    result = await optimizer.solve(
        data_provider=data_provider,
        preference_weights=PreferenceWeights(),
    )

    # 7. Assertion
    print("\n--- TEST 2: COMPLIANCE SAFETY NET ---")

    assert result.optimal_schedule is not None

    # Check for assignment safely
    assignments = result.optimal_schedule.shift_assignments.get(shift.shift_key, [])

    if result.success and 456 in assignments:
        print("SUCCESS: Solver assigned RN Sue despite her preference.")
        print("Reason: HPRD Compliance took priority over Preference.")
    else:
        print(f"FAILURE. Infeasibility: {result.infeasibility_reason}")

    assert result.success is True
    assert 456 in assignments
