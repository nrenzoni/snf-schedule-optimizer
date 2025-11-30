import random
import uuid
from typing import List, Optional, Tuple

import pendulum
from dependency_injector import containers, providers
from dependency_injector.providers import DependenciesContainer

from snf_schedule_optimizer.models import (
    Employee,
    FacilityConfig,
    FacilityHrConfig,
    MinMandates,
    NurseProfile,
    OvertimeTrigger,
    PerShiftStressTestParameters,
    PunchType,
    ResidentAcuity,
    Shift,
    ShiftSpecificRequirements,
    StaffCompensationRecord,
    TimePunch,
)
from snf_schedule_optimizer.models.testing import MockCertificationRecord
from snf_schedule_optimizer.persistence import NurseRetrieverStaticListImpl
from snf_schedule_optimizer.persistence import CertificationServiceStaticListImpl
from snf_schedule_optimizer.persistence import EmployeeRetrieverStaticListImpl
from snf_schedule_optimizer.persistence import FacilityRulesServiceStaticListImpl
from snf_schedule_optimizer.persistence import (
    RawHistoryRecord,
    RawHistoryRetrieverStaticListImpl,
)
from snf_schedule_optimizer.persistence import (
    MockDifferentialRule,
    MockOvertimeRule,
    RuleRetrievalServiceStaticListImpl,
)
from snf_schedule_optimizer.persistence import StaffCompensationServiceStaticListImpl
from snf_schedule_optimizer.resident_acuity_retrievers import (
    ResidentAcuityPerShiftRetrieverImpl,
)
from snf_schedule_optimizer.robustness_tests import test_running
from snf_schedule_optimizer.robustness_tests import (
    DefaultNurseSimulateGenerator,
    SimulateFacilityScenarioParams,
)
from snf_schedule_optimizer.services.payroll.calculations.overtime_calculation import (
    OvertimeCalculatorImpl,
)
from snf_schedule_optimizer.services.payroll.calculations.rate_calculations import (
    DifferentialAndOvertimeRateCalculator,
)
from snf_schedule_optimizer.services.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.services.payroll.calculations.shift_slicers import (
    TimeOverlapShiftSlicer,
)
from snf_schedule_optimizer.services.payroll.rules.rule_eligibility_service import (
    RuleEligibilityService,
)
from snf_schedule_optimizer.services.timekeeping.shift_reconciliation import (
    ShiftReconcilerServiceImpl,
)
from snf_schedule_optimizer.services.timekeeping.work_history_service import (
    EmployeeWorkHistoryServiceImpl,
)

N_FORECAST_DAYS = 3
NY_TZ = pendulum.Timezone("America/New_York")

PROVIDED_KEY = "provided"
DEFAULT_KEY = "default"


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
                unit_id=rng.choice(["A", "B"]),
                census_day=pendulum.now(pendulum.UTC),
                pt_score_gg=acuity,
                nta_score=rng.randint(1, 10),
                clinical_category=rng.choice(["Rehab", "LTC"]),
            )
        )
    return residents


class Config(containers.DeclarativeContainer):
    """Configuration parameters for the simulation test, designed for overrides."""

    # Core Configuration
    RNG_SEED = providers.Object(0)

    # Default Shift Generator Parameters (can be overridden)
    N_DAYS = providers.Object(N_FORECAST_DAYS)  # Used by nurse generator
    SHIFT_COUNT = providers.Object(
        N_FORECAST_DAYS
    )  # Used by shift generator (default=N_DAYS)

    TIMEZONE = providers.Object(NY_TZ)
    START_DATE = providers.Object(pendulum.DateTime(2025, 11, 9))

    # Test-Specific Overrides (default to None/empty list)
    # Allows us to inject a static list of nurses for specific tests
    NURSES_LIST = providers.List()  # Default empty list
    # Allows us to inject predefined acuity data
    ACUITY_DATA: providers.Object[Optional[List[ResidentAcuity]]] = providers.Object(
        None
    )  # Default None

    # Stress Test Parameters (Standard for both tests, but can be overridden)
    STRESS_PARAMS = providers.Object(
        PerShiftStressTestParameters(
            admission_surge_factor=0.2,
            high_acuity_mix_increase=0.3,
            staff_call_out_rate=0.05,
        )
    )

    # Nurse Simulation Parameters
    SIM_PARAMS = providers.Object(
        SimulateFacilityScenarioParams(
            rn_base_wage=30.0,
            lpn_base_wage=22.0,
            cna_base_wage=18.0,
            agency_multiplier=2.2,
            turnover_rate=0.3,
        )
    )

    # Mandates (Must be an object provider to allow easy override)
    MANDATES = providers.Object(
        MinMandates(
            min_rn_hprd=0.7,
            min_lpn_hprd=0.75,
            min_cna_hprd=2.5,
            min_total_hprd=2.75,
            min_staff_per_shift_rn=1,
            min_staff_per_shift_lpn=1,
            min_staff_per_shift_cna=2,
        )
    )

    # Facility Configuration
    FACILITY_CONFIG = providers.Object(
        FacilityConfig(
            facility_id="TEST_FACILITY_001",
            shifts_per_day=3,
            overtime_threshold_hours_per_week=40,
            start_of_work_week_day=pendulum.WeekDay.SUNDAY,
            start_of_work_day_time=pendulum.time(7, 0, 0),
            pay_period=pendulum.duration(weeks=2),
            weekend_multiplier=1.25,
            night_shift_multiplier=1.15,
        )
    )

    # HR Configuration
    HR_CONFIG = providers.Object(
        FacilityHrConfig(
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
    )

    # Shift Requirements
    REQUIREMENTS = providers.Object(
        ShiftSpecificRequirements(
            target_hprd_rn=1.0, target_hprd_cna=3.0, target_total_hprd=3.5
        )
    )

    EMPLOYEES: providers.Object[Optional[List[Employee]]] = providers.Object(None)

    # Differential and Overtime Rules
    DIFF_RULES = providers.List(
        providers.Object(MockDifferentialRule("diff1", 10, 10, ["cna"]))
    )
    OT_RULES = providers.List(
        providers.Object(MockOvertimeRule("ot1", 1.01, 10, OvertimeTrigger(), None))
    )

    HISTORY_RECORDS = providers.List()
    CERTIFICATES = providers.List()
    STAFF_COMPENSATION_RECORDS = providers.List()


def select_nurse_source(nurses_list: Optional[List[str]]) -> str:
    return PROVIDED_KEY if bool(nurses_list) else DEFAULT_KEY


def select_acuity_source(acuity_data: Optional[List[ResidentAcuity]]) -> str:
    return PROVIDED_KEY if acuity_data is not None else DEFAULT_KEY


class Container(containers.DeclarativeContainer):
    """Dependency injection container with conditional providers for different test types."""

    config: DependenciesContainer = providers.DependenciesContainer()

    # --- Core Dependencies (RNG, Acuity) ---
    rng = providers.Singleton(random.Random, config.RNG_SEED)

    nurse_simulate_generator_factory = providers.Factory(
        DefaultNurseSimulateGenerator,
        n_employees=providers.Callable(lambda days: days * 500, config.N_DAYS),
        simulation_params=config.SIM_PARAMS,
        rng=rng,
    )

    nurses = providers.Selector(
        providers.Callable(select_nurse_source, config.NURSES_LIST),
        **{
            PROVIDED_KEY: config.NURSES_LIST,
            DEFAULT_KEY: providers.Callable(
                nurse_simulate_generator_factory.provided.generate_nurse_profiles
            ),
        },
    )

    nurse_retriever = providers.Singleton(NurseRetrieverStaticListImpl, nurses)

    generated_acuity = providers.Callable(
        generate_simulated_acuity, config.STRESS_PARAMS, rng
    )

    # 2. Acuity Data Selector: If ACUITY_DATA is provided, use it. Otherwise, generate it.
    simulated_acuity_data = providers.Selector(
        providers.Callable(select_acuity_source, config.ACUITY_DATA),
        **{PROVIDED_KEY: config.ACUITY_DATA, DEFAULT_KEY: generated_acuity},
    )

    resident_acuity_per_shift_retriever = providers.Singleton(
        ResidentAcuityPerShiftRetrieverImpl, simulated_acuity_data
    )

    # --- Nurse Simulation ---
    nurse_simulate_generator = providers.Factory(
        DefaultNurseSimulateGenerator,
        n_employees=providers.Callable(lambda n_days: n_days * 500, config.N_DAYS),
        simulation_params=config.SIM_PARAMS,
        rng=rng,
    )

    employee_retriever = providers.Singleton(
        EmployeeRetrieverStaticListImpl,
        employees=config.EMPLOYEES,
    )

    # --- Shift/Test Generators ---
    stress_case_generator = providers.Singleton(
        test_running.SingleTestRunCaseGenerator, config.STRESS_PARAMS
    )

    # --- Shift Generator (Uses SHIFT_COUNT and N_DAYS now) ---
    shift_generator = providers.Singleton(
        test_running.DefaultShiftGenerator,
        config.START_DATE,
        config.SHIFT_COUNT,  # Use SHIFT_COUNT here for flexibility
        None,
        config.TIMEZONE,
    )

    # --- Payroll/Rule Services ---
    certification_service = providers.Singleton(
        CertificationServiceStaticListImpl,
        records=config.CERTIFICATES,
    )

    rule_retriever_service = providers.Singleton(
        RuleRetrievalServiceStaticListImpl, config.DIFF_RULES, config.OT_RULES
    )

    rule_eligibility_service = providers.Singleton(
        RuleEligibilityService, certification_service, rule_retriever_service
    )

    history_retriever = providers.Singleton(
        RawHistoryRetrieverStaticListImpl,
        records=config.HISTORY_RECORDS,
    )

    facility_rule_service = providers.Singleton(
        FacilityRulesServiceStaticListImpl,
    )

    shift_reconciler_service = providers.Singleton(
        ShiftReconcilerServiceImpl, facility_rules_service=facility_rule_service
    )

    work_history_service = providers.Singleton(
        EmployeeWorkHistoryServiceImpl,
        history_retriever=history_retriever,
        shift_reconciler=shift_reconciler_service,
    )

    ot_calculator = providers.Singleton(OvertimeCalculatorImpl, work_history_service)

    shift_slicer = providers.Singleton(TimeOverlapShiftSlicer)

    rate_calculator = providers.Singleton(DifferentialAndOvertimeRateCalculator)

    staff_compensation_service = providers.Singleton(
        StaffCompensationServiceStaticListImpl,
        records=config.STAFF_COMPENSATION_RECORDS.provided,
    )

    shift_pay_processor = providers.Singleton(
        ShiftPayProcessor,
        eligibility_service=rule_eligibility_service,
        ot_calculator=ot_calculator,
        slicer=shift_slicer,
        rate_calculator=rate_calculator,
        compensation_service=staff_compensation_service,
        work_history_service=work_history_service,
    )

    # --- Test Runner ---
    test_runner = providers.Singleton(
        test_running.TestRunner,
        nurse_retriever=nurse_retriever,
        employee_retriever=employee_retriever,
        resident_acuity_retriever=resident_acuity_per_shift_retriever,
        shift_pay_processor=shift_pay_processor,
        staff_compensation_service=staff_compensation_service,
        seed=config.RNG_SEED,
    )


def test_sim_scenario_1() -> None:
    container = Container(config=Config())
    container.wire(modules=[__name__])

    test_runner = container.test_runner()

    shift_generator = container.shift_generator()
    stress_case_generator = container.stress_case_generator()
    facility_config = container.config.FACILITY_CONFIG()
    facility_hr_config = container.config.HR_CONFIG()
    min_mandates = container.config.MANDATES()

    requirements = ShiftSpecificRequirements(
        target_hprd_rn=1.0, target_hprd_cna=3.0, target_total_hprd=3.5
    )

    run_results = test_runner.run_sensitivity_analysis(
        "test_case_001",
        shift_generator,
        stress_case_generator,
        facility_config,
        facility_hr_config,
        requirements,
        min_mandates,
    )

    print(run_results)

    # def test_two_shifts_cheapest_nurse_selected_each() -> None:
    #     """Test that the cheapest nurse is selected for first shift, and second cheapest for second shift (can't do same nurse back to back shifts)."""
    #
    #     stress_case_generator = test_running.SingleTestRunCaseGenerator(
    #         PerShiftStressTestParameters(
    #             admission_surge_factor=0.2,
    #             high_acuity_mix_increase=0.3,
    #             staff_call_out_rate=0.05
    #         )
    #     )
    #
    #     def build_nurse(nurse_number: int, hourly_cost_base: float) -> NurseProfile:
    #         return NurseProfile(
    #             employee_id=f"N_{nurse_number}",
    #             # role=NurseRole.CNA,
    #             # base_rate=hourly_cost_base,
    #             # ot_multiplier=1.05,
    #             available_hours_weekly=40,
    #             # is_agency=False,
    #             skills=[],
    #             shift_custom_preferences=[]
    #         )
    #
    #     nurse_retriever = NurseRetrieverStaticListImpl(
    #         [
    #             build_nurse(1, 15),  # Cheapest
    #             build_nurse(2, 20),  # Second cheapest
    #             build_nurse(3, 25),  # Most expensive
    #         ]
    #     )
    #
    #     # Minimum mandates set to require only 1 CNA per shift
    #     min_mandates = MinMandates(
    #         min_rn_hprd=0.0,
    #         min_lpn_hprd=0.0,
    #         min_cna_hprd=2.5,
    #         min_total_hprd=0,
    #         min_staff_per_shift_rn=0,
    #         min_staff_per_shift_lpn=0,
    #         min_staff_per_shift_cna=1
    #     )
    #
    #     facility_config = FacilityConfig(
    #         facility_id="TEST_FACILITY_001",
    #         shifts_per_day=3,
    #         overtime_threshold_hours_per_week=40,
    #         start_of_work_week_day=pendulum.WeekDay.SUNDAY,
    #         start_of_work_day_time=pendulum.time(7, 0, 0),
    #         pay_period=pendulum.duration(weeks=2),
    #         weekend_multiplier=1.25,
    #         night_shift_multiplier=1.15
    #     )
    #
    #     shift_generator = test_running.DefaultShiftGenerator(
    #         pendulum.DateTime(2025, 11, 9),  # Sunday
    #         None,
    #         2,
    #         NY_TZ
    #     )
    #
    #     facility_hr_config = FacilityHrConfig(
    #         max_weekly_hours_per_nurse=60,
    #         min_rest_hours_between_shifts=12,
    #         max_consecutive_work_days=5,
    #         max_total_hours_per_pay_period=80,
    #         max_patient_to_staff_ratio=None,
    #         mandatory_days_off_after_max_consecutive_days=None,
    #         max_weekend_shifts_per_month=None,
    #         max_floating_assignments_per_month=None,
    #         max_night_shifts_per_month=None,
    #         require_annual_training=None,
    #     )
    #
    #     predefined_acuity_data = generate_simulated_acuity_deterministic(1)
    #     resident_acuity_per_shift_retriever = ResidentAcuityPerShiftRetrieverImpl(predefined_acuity_data)
    #
    #     test_runner = test_running.TestRunner(
    #         nurse_retriever,
    #         employee_retriever,
    #         resident_acuity_per_shift_retriever,
    #         shift_pay_processor,
    #         staff_compensation_service,
    #         0
    #     )
    #
    #     requirements = ShiftSpecificRequirements(
    #         target_hprd_rn=0,
    #         target_hprd_cna=3.0,
    #         target_total_hprd=0.0
    #     )
    #
    #     run_results = test_runner.run_sensitivity_analysis(
    #         "test_case_002",
    #         shift_generator,
    #         stress_case_generator,
    #         facility_config,
    #         facility_hr_config,
    #         requirements,
    #         min_mandates
    #     )
    #
    #     print(run_results)


def test_two_shifts_cheapest_nurse_selected_each_refactored() -> None:
    """Test that the cheapest nurse is selected for first shift, and second cheapest for second shift (can't do same nurse back to back shifts)."""

    data_provider = TestDataProvider(employee_count=3, rng_seed=42)

    # 1. Define the specific overrides for this test case
    test_case_overrides = {
        "NURSES_LIST": data_provider.nurse_profiles,
        "EMPLOYEES": data_provider.employees,
        "CERTIFICATES": data_provider.certificate_records,
        "STAFF_COMPENSATION_RECORDS": data_provider._compensation_records,
        "HISTORY_RECORDS": data_provider.history_records,
        # Override the mandates to require only 1 CNA
        "MANDATES": MinMandates(
            min_rn_hprd=0.0,
            min_lpn_hprd=0.0,
            min_cna_hprd=2.5,
            min_total_hprd=0,
            min_staff_per_shift_rn=0,
            min_staff_per_shift_lpn=0,
            min_staff_per_shift_cna=1,
        ),
        # Override shift generation length and number of days
        "N_DAYS": 2,  # Two shifts
        "SHIFT_COUNT": 2,  # Total shifts to generate
        "N_FORECAST_DAYS": None,  # Use the count parameter instead
        # Predefined Acuity data (Need a new provider for this data)
        "ACUITY_DATA": generate_simulated_acuity_deterministic(1),
    }

    # 2. Instantiate and configure the container
    container = Container(config=Config())
    container.wire(modules=[__name__])

    container.config.NURSES_LIST.override(
        providers.Object(test_case_overrides["NURSES_LIST"])
    )
    container.config.MANDATES.override(
        providers.Object(test_case_overrides["MANDATES"])
    )
    container.config.N_DAYS.override(providers.Object(test_case_overrides["N_DAYS"]))
    container.config.SHIFT_COUNT.override(
        providers.Object(test_case_overrides["SHIFT_COUNT"])
    )
    container.config.ACUITY_DATA.override(
        providers.Object(test_case_overrides["ACUITY_DATA"])
    )
    container.config.EMPLOYEES.override(
        providers.Object(test_case_overrides["EMPLOYEES"])
    )
    container.config.CERTIFICATES.override(
        providers.Object(test_case_overrides["CERTIFICATES"])
    )
    container.config.STAFF_COMPENSATION_RECORDS.override(
        providers.Object(test_case_overrides["STAFF_COMPENSATION_RECORDS"])
    )
    container.config.HISTORY_RECORDS.override(
        providers.Object(test_case_overrides["HISTORY_RECORDS"])
    )

    # 4. Resolve the TestRunner object and execute
    test_runner = container.test_runner()

    # Resolve the other injected objects
    shift_generator = container.shift_generator()
    stress_case_generator = container.stress_case_generator()
    facility_config = container.config.FACILITY_CONFIG()
    facility_hr_config = container.config.HR_CONFIG()
    min_mandates = container.config.MANDATES()

    # The requirements object is static for this test, so we define it here or configure it in the new setup
    requirements = ShiftSpecificRequirements(
        target_hprd_rn=0, target_hprd_cna=3.0, target_total_hprd=0.0
    )

    run_results = test_runner.run_sensitivity_analysis(
        "test_case_002",
        shift_generator,
        stress_case_generator,
        facility_config,
        facility_hr_config,
        requirements,
        min_mandates,
    )

    print(run_results)


class TestDataProvider:
    """
    Master generator class responsible for creating all interrelated test data
    (Employees, Certs, Profiles, Compensation Records) in the correct sequence.
    """

    def __init__(self, employee_count: int, rng_seed: int = 0):
        self.rng = random.Random(rng_seed)
        self.employee_count = employee_count

        # Final objects accessible via properties
        self._employees: List[Employee] = []
        self._compensation_records: List[StaffCompensationRecord] = []
        self._nurse_profiles: List[NurseProfile] = []
        self._certificate_records: List[Tuple[str, MockCertificationRecord]] = []
        self._raw_history_records: List[RawHistoryRecord] = []

        # Run the full generation pipeline immediately
        self._generate_all_data()

    def _generate_all_data(self) -> None:
        """Executes the sequential generation logic."""

        # 1. Generate Base Employee and Compensation Data
        employee_comp_data = generate_simulated_employees_deterministic(
            self.employee_count
        )
        self._employees = [e for e, c in employee_comp_data]
        self._compensation_records = [c for e, c in employee_comp_data]
        employee_ids = [e.employee_id for e in self._employees]

        # 2. Generate Dependent Data (Certifications and Profiles)
        self._certificate_records = generate_mock_certification_records(
            employee_ids, rng_seed=self.rng.getrandbits(32)
        )
        self._nurse_profiles = self._generate_nurse_profiles_from_comp(
            employee_comp_data
        )

        # 3. NEW STEP: Generate Raw History Records
        self._raw_history_records = self._generate_raw_history(self._employees)

    def _generate_raw_history(
        self, employees: List[Employee]
    ) -> List[RawHistoryRecord]:
        """
        Creates mock raw shift assignments and punches for historical lookback.
        This simulates data retrieved by the IRawHistoryRetriever.
        """
        history: List[RawHistoryRecord] = []

        # Use a fixed date in the past for determinism
        day_in_the_past = pendulum.datetime(2025, 11, 10, tz="UTC")

        for emp in employees:
            # Simulate a standard 8-hour shift in the past
            shift_start = day_in_the_past.add(hours=self.rng.randint(8, 12))
            shift_end = shift_start.add(hours=8)

            shift_id = f"HIST_{emp.employee_id}"

            # 1. Create a Shift Template (for the dictionary key)
            shift_template = Shift(
                shift_id=shift_id,
                shift_start_dt=shift_start,
                shift_end_dt=shift_end,
                # Add minimal necessary fields for the Shift model context
                # employee_id=emp.employee_id,
                shift_number=1,
                day_shift=True,
                day_of_week=pendulum.MONDAY,
                timezone=pendulum.timezone("UTC"),
            )

            # 2. Create corresponding raw punches (simulating a clean 8-hour punch)
            punches = [
                TimePunch(
                    employee_id=emp.employee_id,
                    punch_time=shift_start,
                    raw_punch_id=uuid.uuid4(),
                    punch_type=PunchType.CHECK_IN,
                ),
                TimePunch(
                    employee_id=emp.employee_id,
                    punch_time=shift_end,
                    raw_punch_id=uuid.uuid4(),
                    punch_type=PunchType.CHECK_OUT,
                ),
            ]

            # 3. Add to the list in the required format: (employee_id, Shift, List[TimePunch])
            # NOTE: We use the employee_id in the tuple for the final retrieval service lookup.
            history.append((emp.employee_id, shift_template, punches))

        return history

    def _generate_nurse_profiles_from_comp(
        self,
        employee_comp_data: List[Tuple["Employee", "StaffCompensationRecord"]],
    ) -> List[NurseProfile]:
        """Helper to create NurseProfiles by linking Employee and Compensation data."""
        profiles = []
        for emp, comp in employee_comp_data:
            # NOTE: This assumes you have logic to decide skills/preferences here.
            profiles.append(
                NurseProfile(
                    employee_id=emp.employee_id,
                    # base_rate=comp.base_rate_effective,
                    # ot_multiplier=comp.ot_multiplier,
                    # is_agency=comp.is_agency,
                    available_hours_weekly=40,
                    skills=["BLS"],
                    shift_custom_preferences=[],
                )
            )
        return profiles

    # --- Properties to Expose Final Data Structures ---

    @property
    def history_records(self) -> List[RawHistoryRecord]:
        """Returns the list of (employee_id, Shift, List[TimePunch]) tuples for historical lookups."""
        return self._raw_history_records

    @property
    def employees(self) -> List[Employee]:
        return self._employees

    @property
    def nurse_profiles(self) -> List[NurseProfile]:
        return self._nurse_profiles

    @property
    def certificate_records(self) -> List[Tuple[str, MockCertificationRecord]]:
        return self._certificate_records


def build_cheapest_nurses() -> List[NurseProfile]:
    """Helper to build the specific list of nurses for this test."""

    def build_nurse(nurse_number: int, hourly_cost_base: float) -> NurseProfile:
        # Assuming NurseProfile needs base_rate for cost
        return NurseProfile(
            employee_id=f"N_{nurse_number}",
            # Set minimum attributes required for the test logic
            # base_rate=hourly_cost_base,
            available_hours_weekly=40,
            skills=[],
            shift_custom_preferences=[],
        )

    return [
        build_nurse(1, 15),  # Cheapest
        build_nurse(2, 20),  # Second cheapest
        build_nurse(3, 25),  # Most expensive
    ]


def generate_simulated_acuity_deterministic(
    n_residents: int,
) -> List[ResidentAcuity]:
    """Creates simple acuity records for testing."""
    residents = []

    for i in range(n_residents):
        residents.append(
            ResidentAcuity(
                resident_id=f"R_{i}",
                unit_id="A",
                census_day=pendulum.now(pendulum.UTC),
                pt_score_gg=5,
                nta_score=3,
                clinical_category="Rehab",
            )
        )
    return residents


def generate_simulated_employees_deterministic(
    count: int, start_id: int = 1
) -> List[Tuple[Employee, StaffCompensationRecord]]:
    """
    Creates a deterministic list of Employee records and their associated
    StaffCompensationRecords for controlled testing scenarios.

    :param count: The number of Employee records to create.
    :param start_id: The starting number for the employee IDs.
    :return: A list of (Employee, StaffCompensationRecord) tuples.
    """
    employee_comp_data: List[Tuple[Employee, StaffCompensationRecord]] = []

    # Use fixed values for determinism
    fixed_hire_date = pendulum.datetime(2023, 1, 1, tz="UTC")
    fixed_comp_start_date = pendulum.datetime(2025, 1, 1, tz="UTC").date()
    job_roles = [
        "RN",
        "LPN",
        "CNA",
    ]  # Use string literals instead of enum if not needed here

    # Base rates for deterministic cost calculation
    BASE_WAGES = {"RN": 30.0, "LPN": 22.0, "CNA": 18.0}

    for i in range(count):
        employee_num = start_id + i

        # Cycle through job roles deterministically
        job_title: str = job_roles[i % len(job_roles)]
        employee_id = f"EMP_{employee_num}"

        # Determine compensation details
        base_rate = BASE_WAGES.get(job_title, 15.0)
        is_union = i % 2 == 0  # Deterministic assignment of union status

        # 1. Create Employee (HR Identity)
        employee = Employee(
            employee_id=employee_id,
            name=f"Staff {employee_num} ({job_title})",
            job_title=job_title,
            hire_date=fixed_hire_date,
            # certifications=['BLS', 'ACLS'],
        )

        # 2. Create StaffCompensationRecord (Financial Data)
        compensation = StaffCompensationRecord(
            employee_id=employee_id,
            base_rate_effective=base_rate,
            ot_multiplier=1.5,
            effective_start_date=fixed_comp_start_date,
            is_agency=False,
            union_contract_id="TEST_UNION_CONTRACT" if is_union else None,
        )

        employee_comp_data.append((employee, compensation))

    return employee_comp_data


def generate_mock_certification_records(
    employee_ids: List[str],
    rng_seed: int = 42,
) -> List[Tuple[str, MockCertificationRecord]]:
    """
    Generates a list of (employee_id, MockCertificationRecord) tuples for testing
    the ICertificationService implementation.

    The generated records include common certifications with varied expiration statuses.
    """
    rng = random.Random(rng_seed)
    current_date = pendulum.now("UTC").date()

    # Define common certification types and their typical validity periods (in days)
    cert_templates = {
        "ACLS": 730,  # ~2 years
        "BLS": 730,  # ~2 years
        "WOUND_CARE": 1095,  # ~3 years
        "PALS": 730,
        "IV_THERAPY": 365,  # ~1 year
    }

    records: List[Tuple[str, MockCertificationRecord]] = []

    for emp_id in employee_ids:
        # 1. Mandatory/Primary Certs (Active for all)
        # Give everyone an active BLS and ACLS to start.
        for cert_name in ["BLS", "ACLS"]:
            # Set expiration date 6 months in the future
            future_exp = current_date.add(months=rng.randint(3, 9))
            records.append(
                (
                    emp_id,
                    MockCertificationRecord(
                        certification_name=cert_name, expiration_date=future_exp
                    ),
                )
            )

        # 2. Specialist Certs (Randomly assign and check expiration)
        if rng.random() < 0.3:  # 30% chance of a specialty
            specialty = rng.choice(["WOUND_CARE", "PALS", "IV_THERAPY"])
            validity_days = cert_templates[specialty]

            # Determine expiration status: 25% chance of being expired
            if rng.random() < 0.25:
                # Expired: Set expiration date 6 months in the past
                expiration_date = current_date.subtract(days=rng.randint(30, 180))
            else:
                # Active: Set expiration date 6 months in the future
                expiration_date = current_date.add(days=rng.randint(30, validity_days))

            records.append(
                (
                    emp_id,
                    MockCertificationRecord(
                        certification_name=specialty, expiration_date=expiration_date
                    ),
                )
            )

    return records
