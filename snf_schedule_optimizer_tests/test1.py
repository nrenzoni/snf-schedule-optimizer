import random
from typing import List

import pendulum

from snf_schedule_optimizer.models import (
    FacilityConfig,
    FacilityHrConfig,
    MinMandates,
    NurseProfile, NurseRole, PerShiftStressTestParameters, ResidentAcuity, ShiftSpecificRequirements
)
from snf_schedule_optimizer.nurse_retrievers import NurseRetrieverStaticListImpl
from snf_schedule_optimizer.resident_acuity_retrievers import ResidentAcuityPerShiftRetrieverImpl
from snf_schedule_optimizer.robustness_tests import test_running
from snf_schedule_optimizer.robustness_tests.scenario_generator import (
    DefaultNurseSimulateGenerator,
    SimulateFacilityScenarioParams
)
from snf_schedule_optimizer.services.calculations.shift_pay_processor import ShiftPayProcessor

N_FORECAST_DAYS = 3
NY_TZ = pendulum.Timezone("America/New_York")


def test_sim_scenario_1() -> None:
    stress_case_generator = test_running.SingleTestRunCaseGenerator(
        PerShiftStressTestParameters(
            admission_surge_factor=0.2,
            high_acuity_mix_increase=0.3,
            staff_call_out_rate=0.05,
            # overtime_shift_count_increase=2,
            # budget_variance_max=0.1
        )
    )

    simulate_facility_scenario_params = SimulateFacilityScenarioParams(
        rn_base_wage=30.0,
        lpn_base_wage=22.0,
        cna_base_wage=18.0,
        agency_multiplier=2.2,
        turnover_rate=0.3
    )

    nurse_simulate_generator = DefaultNurseSimulateGenerator(
        n_employees=N_FORECAST_DAYS * 500,
        simulation_params=simulate_facility_scenario_params,
        rng=random.Random(0)
    )

    nurses = nurse_simulate_generator.generate_nurse_profiles()
    nurse_retriever = NurseRetrieverStaticListImpl(nurses)

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
        None,
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

    rng = random.Random(0)

    resident_acuity_per_shift_retriever = ResidentAcuityPerShiftRetrieverImpl(
        generate_simulated_acuity(
            PerShiftStressTestParameters(
                admission_surge_factor=0.2,
                high_acuity_mix_increase=0.3,
                staff_call_out_rate=0.05,
                # overtime_shift_count_increase=2,
                # budget_variance_max=0.1
            ),
            rng
        )
    )

    shift_pay_processor = ShiftPayProcessor()

    test_runner = test_running.TestRunner(
        nurse_retriever,
        resident_acuity_per_shift_retriever,
        shift_pay_processor,
        0
    )

    requirements = ShiftSpecificRequirements(
        target_hprd_rn=1.0,
        target_hprd_cna=3.0,
        target_total_hprd=3.5
    )

    run_results = test_runner.run_sensitivity_analysis(
        "test_case_001",
        shift_generator,
        stress_case_generator,
        facility_config,
        facility_hr_config,
        requirements,
        min_mandates
    )

    print(run_results)


def test_two_shifts_cheapest_nurse_selected_each() -> None:
    """Test that the cheapest nurse is selected for first shift, and second cheapest for second shift (can't do same nurse back to back shifts)."""

    stress_case_generator = test_running.SingleTestRunCaseGenerator(
        PerShiftStressTestParameters(
            admission_surge_factor=0.2,
            high_acuity_mix_increase=0.3,
            staff_call_out_rate=0.05
        )
    )

    def build_nurse(nurse_number: int, hourly_cost_base: float) -> NurseProfile:
        return NurseProfile(
            employee_id=f"N_{nurse_number}",
            role=NurseRole.CNA,
            base_rate=hourly_cost_base,
            ot_multiplier=1.05,
            available_hours_weekly=40,
            is_agency=False,
            skills=[],
            shift_custom_preferences=[]
        )

    nurse_retriever = NurseRetrieverStaticListImpl(
        [
            build_nurse(1, 15),  # Cheapest
            build_nurse(2, 20),  # Second cheapest
            build_nurse(3, 25),  # Most expensive
        ]
    )

    # Minimum mandates set to require only 1 CNA per shift
    min_mandates = MinMandates(
        min_rn_hprd=0.0,
        min_lpn_hprd=0.0,
        min_cna_hprd=2.5,
        min_total_hprd=0,
        min_staff_per_shift_rn=0,
        min_staff_per_shift_lpn=0,
        min_staff_per_shift_cna=1
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
        None,
        2,
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

    predefined_acuity_data = generate_simulated_acuity_deterministic(1)
    resident_acuity_per_shift_retriever = ResidentAcuityPerShiftRetrieverImpl(predefined_acuity_data)

    shift_pay_processor = ShiftPayProcessor()

    test_runner = test_running.TestRunner(
        nurse_retriever,
        resident_acuity_per_shift_retriever,
        shift_pay_processor,
        0
    )

    requirements = ShiftSpecificRequirements(
        target_hprd_rn=0,
        target_hprd_cna=3.0,
        target_total_hprd=0.0
    )

    run_results = test_runner.run_sensitivity_analysis(
        "test_case_002",
        shift_generator,
        stress_case_generator,
        facility_config,
        facility_hr_config,
        requirements,
        min_mandates
    )

    print(run_results)


def generate_simulated_acuity_deterministic(
        n_residents: int,
) -> List[ResidentAcuity]:
    """Creates simple acuity records for testing."""
    residents = []

    for i in range(n_residents):
        residents.append(
            ResidentAcuity(
                resident_id=f"R_{i}",
                unit_id='A',
                census_day=pendulum.now(pendulum.UTC),
                pt_score_gg=5,
                nta_score=3,
                clinical_category='Rehab'
            )
        )
    return residents


def generate_simulated_acuity(
        stress_params: PerShiftStressTestParameters,
        rng: random.Random,
) -> List[ResidentAcuity]:
    """Creates acuity records reflecting a stressed clinical demand."""
    residents = []
    # Base population size
    base_count = 100 * (1.0 + stress_params.admission_surge_factor)

    for i in range(int(base_count)):
        # Stress Test: Increase the likelihood of high-cost residents
        high_acuity_prob = 0.15 * (1.0 + stress_params.high_acuity_mix_increase)

        acuity = 15 if rng.random() < high_acuity_prob else 5  # High vs Low score

        residents.append(
            ResidentAcuity(
                resident_id=f"R_{i}",
                unit_id=rng.choice(['A', 'B']),
                census_day=pendulum.now(pendulum.UTC),
                pt_score_gg=acuity,
                nta_score=rng.randint(1, 10),
                clinical_category=rng.choice(['Rehab', 'LTC'])
            )
        )
    return residents
