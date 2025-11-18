import abc
import random

import pendulum
from collections import defaultdict
from dataclasses import dataclass

from snf_schedule_optimizer.baseline_schedule_generator import BaselineScheduleGenerator
from snf_schedule_optimizer.data_models import *
from snf_schedule_optimizer.nurse_shift_hours_tracking import NurseShiftHoursStateTracker
from snf_schedule_optimizer.optimization_engine import (
    INurseRetriever, MLModelOutputsRetrieverImpl, NurseShiftScheduleOptimizer, PreferenceWeights, MlModelOutputs, Shift,
    Schedule
)
from snf_schedule_optimizer.overtime_calculation import BasicOvertimeCalculator, IOvertimeCalculator
from snf_schedule_optimizer.resident_acuity_retrievers import ResidentAcuityPerShiftRetrieverImpl
from snf_schedule_optimizer.robustness_tests.scenario_generator import (
    INurseSimulateGenerator, generate_simulated_acuity,
    SimulateFacilityScenarioParams)
import polars as pl

from snf_schedule_optimizer.shift_requirements_retriever import IShiftRequirementsRetriever, \
    ShiftRequirementsRetrieverImpl


class ITestRunCaseGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_test_cases(self) -> Generator[PerShiftStressTestParameters, None, None]:
        """Yields test cases for robustness testing."""
        pass


class SimpleSingleTestRunCaseGenerator(ITestRunCaseGenerator):
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
            n_forecast_days: int,
            timezone: pendulum.Timezone,
    ) -> None:
        self.start_date = start_date
        self.n_forecast_days = n_forecast_days
        self.timezone = timezone

    def generate_shifts(self) -> List[Shift]:
        n_shifts_per_day = 3
        shift_duration = 24 // n_shifts_per_day  # 8 hours

        sunday_of_current_week = self.start_date.start_of('week').add(days=6)

        shifts = []

        for i in range(self.n_forecast_days):
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

        return shifts


class TestRunner:

    def __init__(
            self,
            nurse_retriever: INurseRetriever,
            seed: int,
    ) -> None:
        self.nurse_retriever = nurse_retriever
        self.rng = random.Random(seed)

    def run_sensitivity_analysis(
            self,
            test_param_name: str,
            shift_generator: IShiftGenerator,
            test_run_case_generator: ITestRunCaseGenerator,
            nurse_simulation_generator: INurseSimulateGenerator,
            facility_config: FacilityConfig,
            facility_hr_config: FacilityHrConfig,
            min_mandates: MinMandates,
    ) -> pl.DataFrame:
        """
        runs comparison scenarios. Returns a Polars DataFrame of aggregated metrics.
        """

        shifts = shift_generator.generate_shifts()

        requirements = ShiftSpecificRequirements(
            target_hprd_rn=1.0,
            target_hprd_cna=3.0,
            target_total_hprd=3.5
        )

        nurses = nurse_simulation_generator.generate_nurse_profiles(
            SimulateFacilityScenarioParams(
                rn_base_wage=30.0,
                lpn_base_wage=22.0,
                cna_base_wage=18.0,
                agency_multiplier=2.2,
                turnover_rate=0.3
            )
        )

        results: List[Dict[str, Any]] = []

        for test_case in test_run_case_generator.generate_test_cases():
            scenario_metrics = self.run_scenario(
                str(test_case),
                shifts,
                nurses,
                test_case,
                facility_config,
                facility_hr_config,
                min_mandates,
                requirements,
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
            nurses: List[NurseProfile],
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
        nurses_per_id = {n.employee_id: n for n in nurses}

        # parameters prioritize cost savings
        user_scheduler_pref_weights: PreferenceWeights = PreferenceWeights(
            ot_avoidance_penalty=10.0,
            team_consistency_penalty=1.0
        )

        resident_acuity_per_shift_retriever = ResidentAcuityPerShiftRetrieverImpl(
            generate_simulated_acuity(
                stress_params,
                self.rng
            )
        )

        shift_requirements_retriever = ShiftRequirementsRetrieverImpl(
            shift_requirements
        )

        ml_model_outputs_retriever = MLModelOutputsRetrieverImpl()

        nurse_shift_schedule_optimizer = NurseShiftScheduleOptimizer(
            resident_acuity_per_shift_retriever,
            shift_requirements_retriever,
            self.nurse_retriever,
            ml_model_outputs_retriever
        )

        optimized_schedule_res = nurse_shift_schedule_optimizer.solve(
            shifts,
            facility_config,
            facility_hr_config,
            min_mandates,
            user_scheduler_pref_weights
        )

        if not optimized_schedule_res.success:
            raise RuntimeError("Optimization failed to produce a schedule.")

        optimal_schedule = optimized_schedule_res.optimal_schedule
        assert optimal_schedule is not None

        overtime_calculator = BasicOvertimeCalculator(facility_config)

        optimal_schedule_call_out_adjusted = self._simulate_call_out_rate_in_schedule(
            optimal_schedule,
            stress_params.staff_call_out_rate
        )

        optimal_cost: float = self._calculate_cost(
            optimal_schedule_call_out_adjusted.schedule,
            shifts_per_id,
            nurses_per_id,
            overtime_calculator
        )

        baseline_schedule_generator = BaselineScheduleGenerator(
            resident_acuity_per_shift_retriever,
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
            nurses_per_id,
            overtime_calculator
        )

        optimal_risk_metrics = self._calc_risk_metrics(
            shifts,
            optimal_schedule_call_out_adjusted.schedule,
            self.nurse_retriever,
            shift_requirements_retriever,
        )
        baseline_risk_metrics = self._calc_risk_metrics(
            shifts,
            baseline_schedule_with_callouts,
            self.nurse_retriever,
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

    @staticmethod
    def _calculate_cost(
            schedule: Schedule,
            shifts: Dict[str, Shift],
            nurses: Dict[str, NurseProfile],
            overtime_calculator: IOvertimeCalculator,
    ) -> float:
        """
        Calculates the total dollar total_cost based on assignments and pay rates.
        """
        nurse_shift_hours_state_tracker_per_nurse: Dict[str, NurseShiftHoursStateTracker] = {}

        # shifts_per_nurse: Dict[str, List[str]] = defaultdict(list)  # {nurse_id: [shift_ids]}
        # for shift_id, assigned_nurse_ids in schedule.shift_assignments.items():
        #     for nurse_id in assigned_nurse_ids:
        #         nurse = nurses[nurse_id]
        #         if nurse_id:
        #             shifts_per_nurse[nurse.employee_id].append(shift_id)

        total_cost = 0.0

        for shift_id, assigned_nurse_ids in schedule.shift_assignments.items():
            assigned_nurses = [n for (k, n) in nurses.items() if k in assigned_nurse_ids]
            for nurse in assigned_nurses:
                if not nurse.employee_id in nurse_shift_hours_state_tracker_per_nurse:
                    nurse_shift_hours_state_tracker_per_nurse[nurse.employee_id] = NurseShiftHoursStateTracker(
                        nurse,
                        overtime_calculator
                    )

                nurse_shift_hr_tracker = nurse_shift_hours_state_tracker_per_nurse[nurse.employee_id]

                shift = shifts[shift_id]

                hour_components = nurse_shift_hr_tracker.record_shift_and_get_hour_components(shift)

                for hour_component in hour_components:
                    base_cost = hour_component.duration_hours * nurse.hourly_cost_base
                    if hour_component.is_ot:
                        base_cost *= nurse.ot_multiplier
                    total_cost += base_cost

        return total_cost

    @dataclass(frozen=True)
    class RiskMetrics:
        regulatory_compliance_score: float  # 0 (worst) to 100 (best)
        staff_wellbeing_index: float  # 0 (worst) to 100 (best)
        # turnover_likelihood_score: float  # 0 (low risk) to 100 (high risk)

    def _calc_risk_metrics(
            self,
            shifts: List[Shift],
            schedule: Schedule,
            nurse_retriever: INurseRetriever,
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
            rn_assigned = [n for n in assigned_nurses if n.role == NurseRole.RN]
            # lpn_assigned = [n for n in assigned_nurses if n.role == NurseRole.LPN]  # LPNs not required
            cna_assigned = [n for n in assigned_nurses if n.role == NurseRole.CNA]
            total_assigned = len(assigned_nurses)

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

            for nurse in assigned_nurses:
                if nurse.custom_preferences is not None:
                    for pref in nurse.custom_preferences:
                        if pref.preference_type == PreferenceType.DAY_SHIFT_PREFERENCE:
                            if not shift.day_shift:
                                staff_wellbeing_misses -= 1
                        if pref.preference_type == PreferenceType.NIGHT_SHIFT_PREFERENCE:
                            if shift.day_shift:
                                staff_wellbeing_misses -= 1
                        if pref.preference_type == PreferenceType.SPECIFIC_DAY_OFF:
                            if pref.specific_day == shift.day_of_week:
                                staff_wellbeing_misses -= 1
                        if pref.preference_type == PreferenceType.WEEKEND_OFF:
                            if pref.specific_day in [pendulum.WeekDay.SATURDAY, pendulum.WeekDay.SUNDAY]:
                                staff_wellbeing_misses -= 1

            regulatory_compliance_score_agg -= regulatory_compliance_misses
            staff_wellbeing_index_agg -= staff_wellbeing_misses

        return TestRunner.RiskMetrics(
            regulatory_compliance_score=max(0.0, regulatory_compliance_score_agg),
            staff_wellbeing_index=max(0.0, staff_wellbeing_index_agg)
        )
