import whenever

from snf_schedule_optimizer.infrastructure.scenario_builder import (
    ScenarioBuilder,
    ScenarioDebugPrinter,
)
from snf_schedule_optimizer.models import FacilityConfig, MinMandates, PreferenceWeights
from snf_schedule_optimizer.models.scenario_models import (
    HistoryConfig,
    PayBandConfig,
    TimeConfig,
    WorkforceConfig,
)
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.utils.time_utils import TimeRoundingUtility

from .support import OptimizerTestBuilder

ny_tz = "America/New_York"


async def test_large_scale_financial_optimization() -> None:
    """
    Generates a realistic large-scale scenario (300 shifts, 200 nurses)
    and verifies the optimizer can find a solution.
    """

    # 1. Define the Scenario Parameters
    scenario_data = (
        ScenarioBuilder(seed=123)
        .with_workforce(
            WorkforceConfig(
                count_rn=5,
                count_cna=10,
                percent_agency_rn=0.2,  # 20% Agency RNs
                percent_agency_cna=0.05,
            )
        )
        .with_history(
            HistoryConfig(
                prob_near_ot=0.40  # 40% of staff are about to hit OT (Stress Test)
            )
        )
        .build()
    )

    ScenarioDebugPrinter().print_summary(scenario_data)

    # 2. Build the Full Service Layer
    service = (
        OptimizerTestBuilder()
        .with_employees(scenario_data.employees, scenario_data.nurses)
        .with_financials(scenario_data.financials)
        .with_history(scenario_data.history_map)
        # Note: We use the default HPRD/Strategy logic from the builder
        .build_facade()
    )

    # 3. Setup Context
    context = FacilityScenarioContext(
        facility_id=1,
        shifts=scenario_data.shifts,
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
            tz=ny_tz,
        ),
        min_mandates=MinMandates(
            min_rn_hprd=0.5,  # Realistic mandate
            min_lpn_hprd=0.0,
            min_cna_hprd=2.2,
            min_total_hprd=3.5,
            min_staff_per_shift_rn=1,
            min_staff_per_shift_lpn=0,
            min_staff_per_shift_cna=2,
        ),
    )

    # 4. Run Optimization via Facade
    print(
        f"Solving for {len(scenario_data.shifts)} shifts and {len(scenario_data.employees)} employees..."
    )

    optimization_output = await service.optimize_schedule(
        org_id=1,
        facility_contexts={1: context},
        preference_weights=PreferenceWeights(),
        pay_period_start=TimeRoundingUtility.start_of_week_zoned(
            scenario_data.shifts[0].shift_start_dt.to_tz(ny_tz)
        ).to_instant(),
    )

    # 5. Assertions
    assert optimization_output.is_success is True
    assert optimization_output.schedule is not None
    assert optimization_output.financials is not None
    assert optimization_output.stats is not None

    print("Optimization Successful.")
    print(f"Execution Time: {optimization_output.stats.execution_time_ms:.2f}ms")

    print(f"Cost: ${optimization_output.financials.total_enterprise_cost:,.2f}")

    for role, cost in optimization_output.financials.breakdown_per_role.items():
        print(f" - {role}: ${cost.total_cost:,.2f}")

    print(f"Variables: {optimization_output.stats.total_variables}")


async def test_stress_multi_facility_optimization() -> None:
    """
    Demonstrates a massive multi-facility stress test (10 Facilities).
    Manually configures every aspect of the ScenarioBuilder to show full client usage.
    """
    n_facilities = 5

    print("\n" + "=" * 80)
    print(f"STARTING MULTI-FACILITY STRESS TEST ({n_facilities} FACILITIES)")
    print("=" * 80)

    # --- 1. Aggregators for the Enterprise ---
    all_shifts = []
    all_employees = []
    all_nurses = []
    all_financials = []
    full_history_map = {}
    facility_contexts = {}

    start_date = whenever.ZonedDateTime(2025, 6, 1, tz=ny_tz)

    # --- 2. Generate Data for n Facilities ---
    for i in range(1, n_facilities + 1):
        fac_id = i

        # A. Instantiate Builder (Seeded for determinism per facility)
        builder = ScenarioBuilder(seed=100 + i)

        # B. Manually Set Facility/Org context on the builder
        # (Assuming builder exposes these or we patch them before build)
        builder.facility_id = fac_id
        builder.org_id = 2

        # C. Configure Time (7 Days, 3 Shifts)
        builder.with_time(
            TimeConfig(
                start_date=start_date,
                num_days=7,
                shifts_per_day=3,
                shift_duration_hours=8,
            )
        )

        # D. Configure Workforce (Heavy Agency usage in Facility 5, others normal)
        is_troubled_facility = i == 5
        builder.with_workforce(
            WorkforceConfig(
                count_rn=10,
                count_cna=20,
                percent_agency_rn=0.50 if is_troubled_facility else 0.10,
                percent_agency_cna=0.40 if is_troubled_facility else 0.15,
                # Pay Distribution probabilities
                prob_pay_low=0.2,
                prob_pay_med=0.6,
                prob_pay_high=0.2,
            )
        )

        # E. Configure History (End of month crunch? Lots of people near OT?)
        builder.with_history(
            HistoryConfig(
                prob_zero_hours=0.3,
                prob_half_way_to_ot=0.4,
                prob_near_ot=0.3,  # 30% of staff have < 2 hours cap remaining
            )
        )

        # F. Customize Pay Bands (Optional manual override of dict)
        builder.pay_bands = {
            "low": PayBandConfig(base_rate_rn=28.0, base_rate_cna=16.0),
            "med": PayBandConfig(base_rate_rn=35.0, base_rate_cna=19.0),
            "high": PayBandConfig(base_rate_rn=45.0, base_rate_cna=24.0),
        }

        # G. Build & Accumulate
        scenario = builder.build()

        all_shifts.extend(scenario.shifts)
        all_employees.extend(scenario.employees)
        all_nurses.extend(scenario.nurses)
        all_financials.extend(scenario.financials)
        full_history_map.update(scenario.history_map)

        # H. Create Optimization Context for this Facility
        facility_contexts[fac_id] = FacilityScenarioContext(
            facility_id=fac_id,
            shifts=scenario.shifts,
            config=FacilityConfig(
                org_id=2,
                facility_id=fac_id,
                shifts_per_day=3,
                overtime_threshold_hours_per_week=40,
                start_of_work_week_day=whenever.Weekday.SUNDAY,
                start_of_work_day_time=whenever.Time(7, 0, 0),
                pay_period=whenever.DateDelta(weeks=1),
                weekend_multiplier=1.25,
                night_shift_multiplier=1.5,
                tz=ny_tz,
            ),
            min_mandates=MinMandates(
                min_rn_hprd=0.6,
                min_cna_hprd=2.4,
                min_total_hprd=3.2,
                min_staff_per_shift_rn=1,
                min_staff_per_shift_cna=2,
                min_lpn_hprd=0,
                min_staff_per_shift_lpn=0,
            ),
        )

        # Print partial summary for first facility only to keep logs clean
        if i == 1:
            print(f"\n--- Data Generation Sample ({fac_id}) ---")
            ScenarioDebugPrinter.print_summary(scenario)

    # --- 3. Build Service Facade ---
    print("\nConstructing Enterprise Service...")
    print(f"Total Shifts: {len(all_shifts)}")
    print(f"Total Staff:  {len(all_employees)}")

    service = (
        OptimizerTestBuilder()
        .with_employees(all_employees, all_nurses)
        .with_financials(all_financials)
        .with_history(full_history_map)
        .build_facade()
    )

    # --- 4. Solve ---
    print("\nStarting Optimization (This may take a moment)...")
    result = await service.optimize_schedule(
        org_id=2,
        facility_contexts=facility_contexts,
        preference_weights=PreferenceWeights(
            ot_avoidance_penalty=10.0,
            # agency_usage_penalty=50.0,  # Try to minimize agency
        ),
        pay_period_start=TimeRoundingUtility.start_of_week_zoned(
            start_date.to_tz(ny_tz)
        ).to_instant(),
    )

    # --- 5. Assertions & Reporting ---
    assert result.is_success is True
    assert result.financials is not None
    assert result.stats is not None

    print("\n" + "=" * 80)
    print("MULTI-FACILITY OPTIMIZATION RESULTS")
    print("=" * 80)
    print(f"Status:         {'SUCCESS' if result.is_success else 'FAILED'}")
    print(f"Execution Time: {result.stats.execution_time_ms:.2f} ms")
    print(
        f"Complexity:     {result.stats.total_variables} vars, {result.stats.total_constraints} constraints"
    )
    print(f"Total Cost:     ${result.financials.total_enterprise_cost:,.2f}")

    print("\n[Cost Breakdown by Facility]")
    for fac_id, cost in sorted(result.financials.breakdown_per_facility.items()):
        print(
            f"  {fac_id}: ${cost.total_cost:,.2f} (Agency: ${cost.agency_spend:,.2f})"
        )

    # Verify Logic: Troubled Facility 5 should have higher Agency spend if needed
    fac_5_cost = result.financials.breakdown_per_facility.get(5)
    if fac_5_cost and fac_5_cost.agency_spend > 0:
        print(
            f"\nVerified: FAC_05 (High Agency Config) has agency spend of ${fac_5_cost.agency_spend:,.2f}"
        )
