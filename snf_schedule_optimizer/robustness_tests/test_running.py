import abc
import random
import pendulum
from dataclasses import dataclass

from snf_schedule_optimizer.baseline_schedule_generator import BaselineScheduleGenerator
from snf_schedule_optimizer.models import *
from snf_schedule_optimizer.ml_output_retrievers import MLModelOutputsRetrieverImpl
from snf_schedule_optimizer.nurse_retrievers import INurseRetriever
from snf_schedule_optimizer.optimization_engine import (
    NurseShiftScheduleOptimizer, Shift, Schedule
)

from snf_schedule_optimizer.persistence.employee_retriever_impl import EmployeeRetrieverStaticListImpl
from snf_schedule_optimizer.persistence.facility_rules_service import FacilityRulesServiceStaticListImpl
from snf_schedule_optimizer.persistence.history_retriever import RawHistoryRetrieverStaticListImpl
from snf_schedule_optimizer.persistence.staff_compensation_service import StaffCompensationServiceStaticListImpl
from snf_schedule_optimizer.resident_acuity_retrievers import IResidentAcuityPerShiftRetriever
import polars as pl

from snf_schedule_optimizer.services.calculations.differential_retrieval import NurseDifferentialRetrieverImpl
from snf_schedule_optimizer.services.calculations.shift_pay_processor import ShiftPayProcessor
from snf_schedule_optimizer.services.calculations.shift_reconciliation import ShiftReconcilerServiceImpl
from snf_schedule_optimizer.services.interfaces import IEmployeeRetriever, IShiftRequirementsRetriever, \
    IStaffCompensationService
from snf_schedule_optimizer.persistence.shift_requirements_retriever import ShiftRequirementsRetrieverImpl


class ITestRunCaseGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_test_cases(self) -> Generator[PerShiftStressTestParameters, None, None]:
        """Yields test cases for robustness testing."""
        pass


class SingleTestRunCaseGenerator(ITestRunCaseGenerator):
    def __init__(self, test_case: PerShiftStressTestParameters) -> None:
        self.test_case = test_case

    def generate_test_cases(self) -> Generator[PerShiftStressTestParameters, None, None]:
        yield self.test_case


class SingleParamPermuteTestRunCaseGenerator(ITestRunCaseGenerator):
    def __init__(
            self,
            param_name: StressTestParameterName,
            test_values: List[Any],
            default_params: dict[str, Any],
    ) -> None:
        self.param_name = param_name
        self.test_values = test_values
        self.default_params = default_params

    def generate_test_cases(self) -> Generator[PerShiftStressTestParameters, None, None]:
        for value in self.test_values:
            try:
                params = self.default_params.copy()
                params[self.param_name] = value
                stress_params = PerShiftStressTestParameters(**params)
            except TypeError:
                stress_params = PerShiftStressTestParameters(**self.default_params)
                if not hasattr(stress_params, self.param_name):
                    raise ValueError(f"Unknown TimeSeriesParameters field: {self.param_name}")
                setattr(stress_params, self.param_name, value)

            yield stress_params


class IShiftGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_shifts(self) -> List[Shift]:
        """Generates shifts for the forecast horizon."""
        pass


class DefaultShiftGenerator(IShiftGenerator):
    def __init__(
            self,
            start_date: pendulum.DateTime,
            n_forecast_days: Optional[int],
            shifts_total: Optional[int],
            timezone: pendulum.Timezone,
    ) -> None:
        if n_forecast_days is None and shifts_total is None:
            raise ValueError("Either n_forecast_days or shifts_total must be provided.")
        if shifts_total is not None and n_forecast_days is not None:
            raise ValueError("Only one of n_forecast_days or shifts_total should be provided.")

        self.start_date = start_date
        self.n_forecast_days = n_forecast_days
        self.shifts_total = shifts_total
        self.timezone = timezone

    def generate_shifts(self) -> List[Shift]:
        n_shifts_per_day = 3
        shift_duration = 24 // n_shifts_per_day  # 8 hours

        sunday_of_current_week = self.start_date.start_of('week').add(days=6)

        if self.shifts_total is not None:
            n_forecast_days = (self.shifts_total + n_shifts_per_day - 1) // n_shifts_per_day
        else:
            assert self.n_forecast_days is not None
            n_forecast_days = self.n_forecast_days

        shifts = []

        for i in range(n_forecast_days):
            for j in range(n_shifts_per_day):
                shift_start_hour = 7 if j == 0 else (15 if j == 1 else 23)
                shift_start_time = sunday_of_current_week.add(days=i).add(hours=shift_start_hour)
                shift_end_time = shift_start_time.add(hours=shift_duration)
                shifts.append(
                    Shift(
                        shift_id=f"SHIFT_{i * n_shifts_per_day + j + 1}",
                        shift_number=i * n_shifts_per_day + j + 1,
                        day_shift=(j == 0),
                        day_of_week=pendulum.WeekDay((i - 1) % 7),  # 1=Sun, 7=Sat
                        shift_start_dt=shift_start_time,
                        shift_end_dt=shift_end_time,
                        timezone=self.timezone
                    )
                )
                if self.shifts_total is not None:
                    if len(shifts) >= self.shifts_total:
                        return shifts

        return shifts


class TestRunner:

    def __init__(
            self,
            nurse_retriever: INurseRetriever,
            employee_retriever: IEmployeeRetriever,
            resident_acuity_retriever: IResidentAcuityPerShiftRetriever,
            shift_pay_processor: ShiftPayProcessor,
            staff_compensation_service: IStaffCompensationService,
            seed: int,
    ) -> None:
        self.nurse_retriever = nurse_retriever
        self.employee_retriever = employee_retriever
        self.resident_acuity_retriever = resident_acuity_retriever
        self.shift_pay_processor = shift_pay_processor
        self.staff_compensation_service = staff_compensation_service

        self.rng = random.Random(seed)

    def run_sensitivity_analysis(
            self,
            test_param_name: str,
            shift_generator: IShiftGenerator,
            test_run_case_generator: ITestRunCaseGenerator,
            facility_config: FacilityConfig,
            facility_hr_config: FacilityHrConfig,
            shift_specific_requirements: ShiftSpecificRequirements,
            min_mandates: MinMandates,
    ) -> pl.DataFrame:
        """
        runs comparison scenarios. Returns a Polars DataFrame of aggregated metrics.
        """

        shifts = shift_generator.generate_shifts()

        results: List[Dict[str, Any]] = []

        for test_case in test_run_case_generator.generate_test_cases():
            scenario_metrics = self.run_scenario(
                str(test_case),
                shifts,
                test_case,
                facility_config,
                facility_hr_config,
                min_mandates,
                shift_specific_requirements,
            )
            scenario_metrics[test_param_name] = str(test_case)
            results.append(scenario_metrics)

        # Order columns: parameter first, then metrics
        df = pl.DataFrame(results)
        if test_param_name in df.columns:
            cols = [test_param_name] + [c for c in df.columns if c != test_param_name]
            df = df.select(cols)

        return df

    def run_scenario(
            self,
            scenario_id: str,
            shifts: List[Shift],
            stress_params: PerShiftStressTestParameters,
            facility_config: FacilityConfig,
            facility_hr_config: FacilityHrConfig,
            min_mandates: MinMandates,
            shift_requirements: ShiftSpecificRequirements,
    ) -> Dict[str, Any]:
        """
        Runs a single scenario to generate both forward- and backward-looking data.
        """

        shifts_per_id = {s.shift_id: s for s in shifts}

        # parameters prioritize cost savings
        user_scheduler_pref_weights: PreferenceWeights = PreferenceWeights(
            ot_avoidance_penalty=10.0,
            team_consistency_penalty=1.0
        )

        shift_requirements_retriever = ShiftRequirementsRetrieverImpl(
            shift_requirements
        )

        ml_model_outputs_retriever = MLModelOutputsRetrieverImpl()

        nurse_differential_retriever = NurseDifferentialRetrieverImpl(
            facility_config
        )

        nurse_shift_schedule_optimizer = NurseShiftScheduleOptimizer(
            self.resident_acuity_retriever,
            shift_requirements_retriever,
            self.nurse_retriever,
            ml_model_outputs_retriever,
            nurse_differential_retriever,
            self.shift_pay_processor,
            self.employee_retriever,
            self.staff_compensation_service,
        )

        optimized_schedule_res = nurse_shift_schedule_optimizer.solve(
            shifts,
            facility_config,
            facility_hr_config,
            min_mandates,
            user_scheduler_pref_weights
        )

        if not optimized_schedule_res.success:
            if optimized_schedule_res.infeasibility_reason is not None:
                raise RuntimeError(
                    f"Optimization failed due to infeasibility: "
                    f"{optimized_schedule_res.infeasibility_reason}"
                )
            raise RuntimeError("Optimization failed to produce a schedule.")

        optimal_schedule = optimized_schedule_res.optimal_schedule
        assert optimal_schedule is not None

        # post-schedule generation, adjust for call-out
        optimal_schedule_call_out_adjusted = self._simulate_call_out_rate_in_schedule(
            optimal_schedule,
            stress_params.staff_call_out_rate
        )

        # overtime_calculator = OvertimeCalculatorImpl(facility_config)
        # all_nurse_shift_hours_tracker = AllNurseShiftHoursTracker(overtime_calculator)

        optimal_cost: float = self._calculate_cost(
            optimal_schedule_call_out_adjusted.schedule,
            shifts_per_id,
        )

        baseline_schedule_generator = BaselineScheduleGenerator(
            self.resident_acuity_retriever,
            self.nurse_retriever
        )

        baseline_schedule = baseline_schedule_generator.generate_baseline_schedule(shifts)

        baseline_schedule_call_out_adjusted = self._simulate_call_out_rate_in_schedule(
            baseline_schedule,
            stress_params.staff_call_out_rate
        )

        baseline_schedule_with_callouts = baseline_schedule_call_out_adjusted.schedule

        baseline_cost: float = self._calculate_cost(
            baseline_schedule_with_callouts,
            shifts_per_id,
        )

        optimal_risk_metrics = self._calc_risk_metrics(
            shifts,
            optimal_schedule_call_out_adjusted.schedule,
            shift_requirements_retriever,
        )
        baseline_risk_metrics = self._calc_risk_metrics(
            shifts,
            baseline_schedule_with_callouts,
            shift_requirements_retriever
        )

        # Calculate savings
        cost_savings_pct = (1.0 - optimal_cost / baseline_cost) * 100

        # Note: Return type is Dict[str, Any] as metrics can be floats, ints, or strings
        row_results = {
            'Scenario_ID'         : scenario_id,
            'Baseline_Cost'       : baseline_cost,
            'Optimized_Cost'      : optimal_cost,
            'Cost_Savings_Percent': cost_savings_pct
        }

        row_results.update(
            {
                'Baseline_Regulatory_Compliance_Score' : baseline_risk_metrics.regulatory_compliance_score,
                'Optimized_Regulatory_Compliance_Score': optimal_risk_metrics.regulatory_compliance_score,
                'Baseline_Staff_Wellbeing_Index'       : baseline_risk_metrics.staff_wellbeing_index,
                'Optimized_Staff_Wellbeing_Index'      : optimal_risk_metrics.staff_wellbeing_index
            }
        )

        return row_results

    @dataclass(frozen=True)
    class ScheduleWithCallOut:
        schedule: Schedule
        call_outs: Dict[str, List[str]]  # {Shift: [employee_ids who called out]}

    def _simulate_call_out_rate_in_schedule(
            self,
            schedule: Schedule,
            call_out_rate: float,
    ) -> ScheduleWithCallOut:
        """Simulates staff call-outs in the given schedule based on the call-out rate."""
        shift_assignments_with_call_out: Dict[str, List[str]] = {}
        called_out_per_shift: Dict[str, List[str]] = {}
        for shift_id, staff_ids in schedule.shift_assignments.items():
            adjusted_staff_ids = [
                staff_id for staff_id in staff_ids
                if self.rng.random() > call_out_rate
            ]
            called_out_staff = list(set(staff_ids) - set(adjusted_staff_ids))
            called_out_per_shift[shift_id] = called_out_staff
            shift_assignments_with_call_out[shift_id] = adjusted_staff_ids

        return self.ScheduleWithCallOut(
            schedule=Schedule(shift_assignments_with_call_out),
            call_outs=called_out_per_shift
        )

    @staticmethod
    def _generate_baseline_schedule(residents: Any) -> Dict[Any, Any]:
        """Mocks the facility's existing, often inefficient, manual scheduling heuristic."""
        # Simple mock implementation returning an empty schedule dict
        return {}

    def _calculate_cost(
            self,
            schedule: Schedule,
            shifts: Dict[str, Shift],
    ) -> float:
        """
        Calculates the total dollar total_cost based on assignments and pay rates.
        """
        total_cost = 0.0

        employees = set(self.employee_retriever.get_all_employees())

        for shift_id, assigned_employee_ids in schedule.shift_assignments.items():
            shift = shifts[shift_id]
            assigned_employees = [ee for ee in employees if ee.employee_id in assigned_employee_ids]
            for employee in assigned_employees:
                shift_cost = self.shift_pay_processor.calculate_shift_cost(employee, shift)
                total_cost += shift_cost

        return total_cost

    @dataclass(frozen=True)
    class RiskMetrics:
        regulatory_compliance_score: float  # 0 (worst) to 100 (best)
        staff_wellbeing_index: float  # 0 (worst) to 100 (best)
        # turnover_likelihood_score: float  # 0 (low risk) to 100 (high risk)
        overtime_hours_to_total_hours_ratio: int  # ratio of overtime hours to total hours worked, for all nurses

    def _calc_risk_metrics(
            self,
            shifts: List[Shift],
            schedule: Schedule,
            shift_requirements_retriever: IShiftRequirementsRetriever,
    ) -> RiskMetrics:
        """
        quantify non-financial risk.
        """

        regulatory_compliance_score_agg = 100.0
        staff_wellbeing_index_agg = 100.0

        for shift in shifts:

            shift_specific_requirements = shift_requirements_retriever.get_shift_requirements(shift)
            nurses = self.nurse_retriever.get_nurses(shift)

            assigned_nurse_ids = schedule.shift_assignments[shift.shift_id]
            assigned_nurses = [n for n in nurses if n.employee_id in assigned_nurse_ids]

            employee_map = {
                n.employee_id: self.employee_retriever.get_employee_by_id(n.employee_id)
                for n in assigned_nurses
            }

            rn_assigned = []
            # lpn_assigned = []  # LPNs not required
            cna_assigned = []
            total_assigned = len(assigned_nurses)

            for nurse_profile in assigned_nurses:
                employee = employee_map.get(nurse_profile.employee_id)
                if employee is None:
                    continue  # Skip if no corresponding Employee record is found (HR issue)

                # Use employee.job_title for classification
                if employee.job_title == NurseRole.RN:
                    rn_assigned.append(nurse_profile)
                elif employee.job_title == NurseRole.CNA:
                    cna_assigned.append(nurse_profile)
                # Add LPN check here if needed

            required_rn = shift_specific_requirements.target_hprd_rn
            required_cna = shift_specific_requirements.target_hprd_cna
            # required_total = shift_requirements.target_total_hprd

            rn_diff = len(rn_assigned) - required_rn
            cna_diff = len(cna_assigned) - required_cna
            # total_diff = total_assigned - required_total

            regulatory_compliance_misses = 0.0

            if rn_diff < 0:
                regulatory_compliance_misses += rn_diff
            # if lpn_diff < 0:
            #     regulatory_compliance_misses += lpn_diff
            if cna_diff < 0:
                regulatory_compliance_misses += cna_diff
            # if total_diff < 0:
            #     regulatory_compliance_misses += total_diff

            staff_wellbeing_misses = 0

            current_shift_day_value = shift.day_of_week.value  # Get the integer value once

            for nurse_profile in assigned_nurses:
                if nurse_profile.shift_custom_preferences is not None:
                    for pref in nurse_profile.shift_custom_preferences:
                        if pref.preference_type == PreferenceType.DAY_SHIFT_PREFERENCE:
                            if not shift.day_shift:
                                staff_wellbeing_misses -= 1
                        if pref.preference_type == PreferenceType.NIGHT_SHIFT_PREFERENCE:
                            if shift.day_shift:
                                staff_wellbeing_misses -= 1
                        if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                            try:
                                pref_day_int = int(pref.specific_value) if pref.specific_value is not None else -1
                            except (ValueError, TypeError):
                                pref_day_int = -1  # Treat invalid input as non-matching

                            if pref_day_int == current_shift_day_value:
                                staff_wellbeing_misses -= 1
                        if pref.preference_type == PreferenceType.WEEKEND_OFF:
                            if current_shift_day_value in {
                                pendulum.WeekDay.SATURDAY.value,
                                pendulum.WeekDay.SUNDAY.value
                            }:
                                staff_wellbeing_misses -= 1

            regulatory_compliance_score_agg -= regulatory_compliance_misses
            staff_wellbeing_index_agg -= staff_wellbeing_misses

        return TestRunner.RiskMetrics(
            regulatory_compliance_score=max(0.0, regulatory_compliance_score_agg),
            staff_wellbeing_index=max(0.0, staff_wellbeing_index_agg),
            overtime_hours_to_total_hours_ratio=0  # Placeholder implementation
        )
