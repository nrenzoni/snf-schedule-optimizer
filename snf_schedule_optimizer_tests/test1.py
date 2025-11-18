import pendulum
import pytest

from snf_schedule_optimizer.data_models import (
    FacilityConfig,
    FacilityHrConfig,
    MinMandates,
    PerShiftStressTestParameters
)
from snf_schedule_optimizer.optimization_engine import NurseRetrieverImpl
from snf_schedule_optimizer.robustness_tests import test_running
from snf_schedule_optimizer.robustness_tests.scenario_generator import (
    DefaultNurseSimulateGenerator,
    SimulateFacilityScenarioParams
)

N_FORECAST_DAYS = 3
NY_TZ = pendulum.Timezone("America/New_York")


def test_sim_scenario_1() -> None:
    nurse_simulate_generator = DefaultNurseSimulateGenerator(
        n_nurses=N_FORECAST_DAYS * 500,
        seed=0
    )

    stress_case_generator = test_running.SimpleSingleTestRunCaseGenerator(
        PerShiftStressTestParameters(
            admission_surge_factor=0.2,
            high_acuity_mix_increase=0.3,
            staff_call_out_rate=0.05,
            overtime_shift_count_increase=2,
            budget_variance_max=0.1
        )
    )

    simulate_facility_scenario_params = SimulateFacilityScenarioParams(
        rn_base_wage=30.0,
        lpn_base_wage=22.0,
        cna_base_wage=18.0,
        agency_multiplier=2.2,
        turnover_rate=0.3
    )

    test_runner = test_running.TestRunner(
        NurseRetrieverImpl(
            nurse_simulate_generator.generate_nurse_profiles(
                simulate_facility_scenario_params
            )
        ),
        0
    )

    min_mandates = MinMandates(
        min_rn_hprd=0.7,
        min_lpn_hprd=0.75,
        min_cna_hprd=2.5,
        min_total_hprd=2.75,
        min_staff_per_shift_rn=1,
        min_staff_per_shift_lpn=1,
        min_staff_per_shift_cna=2
    )

    facility_config = FacilityConfig(
        facility_id="TEST_FACILITY_001",
        shifts_per_day=3,
        overtime_threshold_hours_per_week=40,
        start_of_work_week_day=pendulum.WeekDay.SUNDAY,
        start_of_work_day_time=pendulum.time(7, 0, 0),
        pay_period=pendulum.duration(weeks=2),
        weekend_multiplier=1.25,
        night_shift_multiplier=1.15
    )

    shift_generator = test_running.DefaultShiftGenerator(
        pendulum.DateTime(2025, 11, 9),  # Sunday
        N_FORECAST_DAYS,
        NY_TZ
    )

    facility_hr_config = FacilityHrConfig(
        max_weekly_hours_per_nurse=60,
        min_rest_hours_between_shifts=12,
        max_consecutive_work_days=5,
        max_total_hours_per_pay_period=80,
        max_patient_to_staff_ratio=None,
        mandatory_days_off_after_max_consecutive_days=None,
        max_weekend_shifts_per_month=None,
        max_floating_assignments_per_month=None,
        max_night_shifts_per_month=None,
        require_annual_training=None,
    )

    run_results = test_runner.run_sensitivity_analysis(
        "test_case_001",
        shift_generator,
        stress_case_generator,
        nurse_simulate_generator,
        facility_config,
        facility_hr_config,
        min_mandates
    )

    print(run_results)
