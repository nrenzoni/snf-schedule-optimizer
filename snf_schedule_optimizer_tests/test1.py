import pendulum
import pytest

from snf_schedule_optimizer.data_models import StressTestParameters
from snf_schedule_optimizer.robustness_tests import test_running

# N_FORECAST_AHEAD_DAYS = 14
NY_TZ = pendulum.Timezone("America/New_York")


def test_test_runner_run1():
    test_runner = test_running.TestRunner()

    shift_generator = test_running.DefaultShiftGenerator(
        pendulum.DateTime(2025, 11, 9),
        3,
        NY_TZ
    )

    stress_case_generator = test_running.SimpleSingleTestRunCaseGenerator(
        StressTestParameters(
            admission_surge_factor=0.2,
            high_acuity_mix_increase=0.3,
            staff_call_out_rate=0.05,
            overtime_shift_count_increase=2,
            budget_variance_max=0.1
        )
    )

    run_results = test_runner.run_sensitivity_analysis(
        "test_case_001",
        shift_generator,
        stress_case_generator
    )
