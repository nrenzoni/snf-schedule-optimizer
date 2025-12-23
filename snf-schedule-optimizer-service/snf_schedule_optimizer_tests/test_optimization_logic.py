import whenever

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    HprdEnforcedRole,
    NurseProfile,
    PreferenceWeights,
    Shift,
    ShiftKey,
    StaffCompensationRecord,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.optimizer.strategies.constraints import (
    ConsecutiveShiftFatigueStrategy,
)
from snf_schedule_optimizer.persistence.fakes import FakeHprdRequirementCalculator
from snf_schedule_optimizer.utils.time_utils import TimeRoundingUtility

from .test_builder import OptimizerTestBuilder

tz_ny = "America/New_York"


async def test_cheapest_nurse_selection_with_fatigue() -> None:
    """
    Replaces: test_two_shifts_cheapest_nurse_selected_each_refactored

    Scenario:
    - 2 Back-to-Back Shifts (Shift 1 -> Shift 2).
    - 3 Nurses with different rates ($15, $20, $25).
    - Constraint: Nurses cannot work back-to-back (Fatigue Rule).

    Expected Outcome:
    - Shift 1: Assigned to Nurse 1 ($15) - The cheapest option.
    - Shift 2: Assigned to Nurse 2 ($20) - The next cheapest (since N1 is tired).
    - Nurse 3 ($25) is left unassigned.
    """
    ref_date = whenever.ZonedDateTime(2025, 1, 1, tz=tz_ny)

    or_id = "ORG_1"

    # 1. Setup Shifts (Back-to-Back)
    shift_1 = Shift(
        org_id=or_id,
        shift_key=ShiftKey(
            facility_id="FAC_1",
            shift_id="SHIFT_1",
        ),
        shift_start_dt=ref_date.add(hours=7),
        shift_end_dt=ref_date.add(hours=15),  # 7am - 3pm
        shift_number=1,
        day_shift=True,
        day_of_week=ref_date.date().day_of_week(),
        unit_id=None,
        is_scheduled=True,
    )

    shift_2 = Shift(
        org_id=or_id,
        shift_key=ShiftKey(
            facility_id="FAC_1",
            shift_id="SHIFT_2",
        ),
        shift_start_dt=ref_date.add(hours=15),
        shift_end_dt=ref_date.add(hours=23),  # 3pm - 11pm (0 gap)
        shift_number=2,
        day_shift=False,
        day_of_week=ref_date.date().day_of_week(),
        unit_id=None,
        is_scheduled=True,
    )

    # 2. Setup Nurses (Sorted by Cost)
    # Nurse 1: $15 (Cheapest)
    n1 = Employee(
        employee_id="N_15",
        name="Cheap",
        job_title="CNA",
        hire_date=ref_date.date(),
    )
    c1 = StaffCompensationRecord(
        employee_id="N_15",
        base_rate_effective=15.0,
        effective_start_date=ref_date.date(),
        ot_multiplier=1.5,
        is_agency=False,
    )
    p1 = NurseProfile(
        employee_id="N_15",
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )

    # Nurse 2: $20 (Mid)
    n2 = Employee(
        employee_id="N_20",
        name="Mid",
        job_title="CNA",
        hire_date=ref_date.date(),
    )
    c2 = StaffCompensationRecord(
        employee_id="N_20",
        base_rate_effective=20.0,
        effective_start_date=ref_date.date(),
        ot_multiplier=1.5,
        is_agency=False,
    )
    p2 = NurseProfile(
        employee_id="N_20",
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )

    # Nurse 3: $25 (Expensive)
    n3 = Employee(
        employee_id="N_25",
        name="Exp",
        job_title="CNA",
        hire_date=ref_date.date(),
    )
    c3 = StaffCompensationRecord(
        employee_id="N_25",
        base_rate_effective=25.0,
        effective_start_date=ref_date.to_tz(tz_ny).date(),
        ot_multiplier=1.5,
        is_agency=False,
    )
    p3 = NurseProfile(
        employee_id="N_25",
        available_hours_weekly=40,
        skills=["CNA"],
        shift_custom_preferences=[],
    )

    # 3. Configure HPRD to force 1 CNA per shift
    fake_hprd = FakeHprdRequirementCalculator(
        requirements_map={
            ("SHIFT_1", HprdEnforcedRole.CNA): 1.0,
            ("SHIFT_2", HprdEnforcedRole.CNA): 1.0,
        }
    )

    optimize_builder = (
        OptimizerTestBuilder()
        .with_employees([n1, n2, n3], [p1, p2, p3])
        .with_financials([c1, c2, c3])
        .with_hprd_calculator(fake_hprd)
        # Explicitly ensure Fatigue Rule is active
        .with_strategies(
            constraints=[
                ConsecutiveShiftFatigueStrategy(),
                # Note: In real app, add HprdStaffingConstraintStrategy too if overrides clear defaults
            ]
        )
    )

    optimizer = optimize_builder.build_optimizer()

    # 5. Solve
    context = FacilityScenarioContext(
        facility_id="FAC_1",
        shifts=[shift_1, shift_2],
        config=FacilityConfig(
            org_id="ORG_1",
            facility_id="FAC_1",
            shifts_per_day=3,
            overtime_threshold_hours_per_week=40,
            start_of_work_week_day=whenever.MONDAY,
            start_of_work_day_time=whenever.Time(7, 0, 0),
            pay_period=whenever.DateTimeDelta(weeks=1),
            weekend_multiplier=1.0,
            night_shift_multiplier=1.0,
            tz=tz_ny,
        ),
        min_mandates=None,  # Handled by fake HPRD
    )

    data_provider = optimize_builder.factory.create(  # Use internal factory pattern or pass manually
        org_id="ORG_1",
        facility_contexts={"FAC_1": context},
        pay_period_start=TimeRoundingUtility.start_of_week_zoned(
            ref_date.to_tz(tz_ny)
        ).to_instant(),
        optimization_start_time=ref_date.to_instant(),
    )

    result = await optimizer.solve(
        data_provider=data_provider,
        preference_weights=PreferenceWeights(),
    )

    # 6. Assertions
    assert result.success
    assert result.optimal_schedule is not None
    assignments = result.optimal_schedule.shift_assignments

    org_id = data_provider.get_org_id()

    # Verify Shift 1 went to cheapest
    assert "N_15" in assignments[ShiftKey(org_id, "SHIFT_1")], (
        "Shift 1 should go to cheapest nurse (N_15)"
    )

    # Verify Shift 2 went to next cheapest (N_15 blocked by fatigue)
    assert "N_20" in assignments[ShiftKey(org_id, "SHIFT_2")], (
        "Shift 2 should go to next cheapest (N_20)"
    )

    # Verify Expensive nurse unused
    assert "N_25" not in assignments.get(ShiftKey(org_id, "SHIFT_1"), [])
    assert "N_25" not in assignments.get(ShiftKey(org_id, "SHIFT_2"), [])
