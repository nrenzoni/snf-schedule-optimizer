import pendulum

from snf_schedule_optimizer.models import FacilityConfig, MinMandates, PreferenceWeights
from snf_schedule_optimizer.optimizer.context import FacilityScenarioContext
from snf_schedule_optimizer.schedule_cost_evaluator import ScheduleCostEvaluator

from .builders import OptimizerTestBuilder
from .scenario_builder import ScenarioBuilder
from .scenario_models import HistoryConfig, WorkforceConfig


def test_large_scale_financial_optimization() -> None:
    """
    Generates a realistic large-scale scenario (300 shifts, 200 nurses)
    and verifies the optimizer can find a solution.
    """

    # 1. Define the Scenario Parameters
    scenario_data = (
        ScenarioBuilder(seed=123)
        .with_workforce(
            WorkforceConfig(
                count_rn=50,
                count_cna=150,
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

    # 2. Build the Optimizer using the Data
    builder = (
        OptimizerTestBuilder()
        .with_employees(scenario_data.employees, scenario_data.nurses)
        .with_financials(scenario_data.financials)
        .with_history(scenario_data.history_map)
        # Note: We use the default HPRD/Strategy logic from the builder)
    )

    optimizer = builder.build()

    # 3. Setup Context
    context = FacilityScenarioContext(
        facility_id="FAC_1",
        shifts=scenario_data.shifts,
        config=FacilityConfig(
            org_id="ORG_1",
            facility_id="FAC_1",
            shifts_per_day=3,
            overtime_threshold_hours_per_week=40,
            start_of_work_week_day=pendulum.WeekDay.MONDAY,
            start_of_work_day_time=pendulum.Time(7, 0, 0),
            pay_period=pendulum.Duration(weeks=1),
            weekend_multiplier=1.5,
            night_shift_multiplier=2.0,
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

    # 4. Solve
    print(
        f"Solving for {len(scenario_data.shifts)} shifts and {len(scenario_data.employees)} employees..."
    )

    result = optimizer.solve(
        org_id="ORG_1",
        facility_contexts={"FAC_1": context},
        preference_weights=PreferenceWeights(),
        pay_period_start=scenario_data.shifts[0].shift_start_dt.start_of("week"),
    )

    # 5. Assertions
    assert result.success is True
    assert result.optimal_schedule is not None

    assert builder.pay_processor is not None
    assert builder.created_provider is not None
    evaluator = ScheduleCostEvaluator(builder.pay_processor)
    financial_report = evaluator.evaluate_schedule(
        result.optimal_schedule,
        builder.created_provider,
    )

    print(f"Optimization Successful. Cost: {financial_report.total_enterprise_cost}")
