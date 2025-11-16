import abc

import pendulum
from collections import defaultdict
from dataclasses import dataclass

from snf_schedule_optimizer.baseline_schedule_generator import BaselineScheduleGenerator
from snf_schedule_optimizer.data_models import *
from snf_schedule_optimizer.nurse_shift_hours_tracking import NurseShiftHoursStateTracker
from snf_schedule_optimizer.optimization_engine import (
    ScheduleOptimizer, PreferenceWeights, MlModelOutputs, Shift, Schedule
)
from snf_schedule_optimizer.overtime_calculation import BasicOvertimeCalculator, IOvertimeCalculator
from snf_schedule_optimizer.robustness_tests.scenario_generator import (
    generate_simulated_acuity,
    generate_simulated_nurses,
    SimulateFacilityScenarioParams)
import polars as pl


class ITestRunCaseGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_test_cases(self) -> Generator[StressTestParameters, None, None]:
        """Yields test cases for robustness testing."""
        pass


class SimpleSingleTestRunCaseGenerator(ITestRunCaseGenerator):
    def __init__(self, test_case: StressTestParameters) -> None:
        self.test_case = test_case

    def generate_test_cases(self) -> Generator[StressTestParameters, None, None]:
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

    def generate_test_cases(self) -> Generator[StressTestParameters, None, None]:
        for value in self.test_values:
            try:
                params = self.default_params.copy()
                params[self.param_name] = value
                stress_params = StressTestParameters(**params)
            except TypeError:
                stress_params = StressTestParameters(**self.default_params)
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
            n_forecast_days_ahead: int,
            timezone: pendulum.Timezone,
    ) -> None:
        self.start_date = start_date
        self.n_forecast_days_ahead = n_forecast_days_ahead
        self.timezone = timezone

    def generate_shifts(self) -> List[Shift]:
        n_shifts_per_day = 3

        sunday_of_current_week = self.start_date.start_of('week').add(days=6)

        shifts = []

        for i in range(1, self.n_forecast_days_ahead + 1):
            for j in range(n_shifts_per_day):
                shift_start_hour = 7 if j == 0 else (19 if j == 1 else 7)
                shift_end_hour = 15 if j == 0 else (7 if j == 1 else 15)
                shifts.append(
                    Shift(
                        shift_id=f"SHIFT_{(i - 1) * n_shifts_per_day + j + 1}",
                        shift_number=(i - 1) * n_shifts_per_day + j + 1,
                        day_shift=(j != 1),
                        day_of_week=DayOfWeek((i - 1) % 7 + 1),  # 1=Mon, 7=Sun
                        shift_start_time=sunday_of_current_week.add(days=i - 1).add(hours=shift_start_hour),
                        shift_end_time=sunday_of_current_week.add(days=i - 1).add(hours=shift_end_hour),
                        timezone=self.timezone
                    )
                )

        return shifts


class TestRunner:

    def run_sensitivity_analysis(
            self,
            test_param_name: str,
            shift_generator: IShiftGenerator,
            test_run_case_generator: ITestRunCaseGenerator,
    ) -> pl.DataFrame:
        """
        runs comparison scenarios. Returns a Polars DataFrame of aggregated metrics.
        """

        shifts = shift_generator.generate_shifts()

        min_mandates = MinMandates(
            min_rn_hprd=0.7,
            min_lpn_hprd=0.75,
            min_cna_hprd=2.5,
            min_total_hprd=2.75,
            min_staff_per_shift_rn=1,
            min_staff_per_shift_lpn=1,
            min_staff_per_shift_cna=2
        )

        results: List[Dict[str, Any]] = []

        for test_case in test_run_case_generator.generate_test_cases():
            # Build TimeSeriesParameters with the varied field; rely on defaults for others.

            requirements = ShiftSpecificRequirements(
                target_hprd_rn=1.0,
                target_hprd_lpn=1.0,
                target_hprd_cna=3.0,
                target_total_hprd=3.5
            )

            facility_config = FacilityConfig(
                facility_id="TEST_FACILITY_001",
                max_consecutive_shifts=6,
                shifts_per_day=3,
                overtime_threshold_hours_per_week=40,
                start_of_work_week_day=pendulum.WeekDay.MONDAY,
                start_of_work_day_time=pendulum.time(7, 0, 0)
            )

            nurses = generate_simulated_nurses(
                SimulateFacilityScenarioParams(
                    cna_base_wage=18.0,
                    agency_multiplier=2.2,
                    turnover_rate=0.3
                )
            )

            scenario_metrics = self.run_scenario(
                str(test_case),
                shifts,
                nurses,
                test_case,
                facility_config,
                min_mandates,
                requirements,
            )

            # Tag with varied parameter value
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
            stress_params: StressTestParameters,
            facility_config: FacilityConfig,
            min_mandates: MinMandates,
            shift_requirements: ShiftSpecificRequirements,
    ) -> Dict[str, Any]:
        """
        Runs a single scenario to generate both forward- and backward-looking data.
        """

        nurses_per_id = {n.employee_id: n for n in nurses}

        stressed_residents: List[ResidentAcuity] = generate_simulated_acuity(stress_params)

        # parameters prioritize cost savings
        user_scheduler_pref_weights: PreferenceWeights = PreferenceWeights(
            ot_avoidance_penalty=10.0,
            team_consistency_penalty=1.0
        )

        model_outputs = MlModelOutputs(
            turnover_risk_scores={},
            shift_call_out_forecast={},
            unit_acuity_stress={},
            team_compatibility_scores={}
        )

        # Assuming solve returns a dict representing the schedule
        optimized_schedule_res = ScheduleOptimizer.solve(
            nurses,
            stressed_residents,
            shifts,
            facility_config,
            min_mandates,
            user_scheduler_pref_weights,
            shift_requirements,
            model_outputs
        )

        if not optimized_schedule_res.success:
            raise RuntimeError("Optimization failed to produce a schedule.")

        optimal_schedule = optimized_schedule_res.optimal_schedule
        assert optimal_schedule is not None

        overtime_calculator = BasicOvertimeCalculator(facility_config)

        optimal_cost: float = self._calculate_cost(optimal_schedule, nurses_per_id, overtime_calculator)

        baseline_schedule = BaselineScheduleGenerator().generate_baseline_schedule(
            shifts,
            stressed_residents,
            nurses
        )

        baseline_cost: float = self._calculate_cost(baseline_schedule, nurses_per_id, overtime_calculator)

        optimal_risk_metrics = self._calc_risk_metrics(shifts, optimal_schedule, nurses, shift_requirements)
        baseline_risk_metrics = self._calc_risk_metrics(shifts, baseline_schedule, nurses, shift_requirements)

        # Calculate savings
        cost_savings_pct = 1 - (optimal_cost / baseline_cost) * 100

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

    @staticmethod
    def _generate_baseline_schedule(residents: Any) -> Dict[Any, Any]:
        """Mocks the facility's existing, often inefficient, manual scheduling heuristic."""
        # Simple mock implementation returning an empty schedule dict
        return {}

    @staticmethod
    def _calculate_cost(
            schedule: Schedule,
            nurses: Dict[str, NurseProfile],
            overtime_calculator: IOvertimeCalculator,
    ) -> float:
        """
        Calculates the total dollar total_cost based on assignments and pay rates.
        """
        nurse_shift_hours_state_tracker_per_nurse: Dict[str, NurseShiftHoursStateTracker] = {}

        shifts_per_nurse: Dict[NurseProfile, List[Shift]] = defaultdict(list)
        for shift, assigned_nurse_ids in schedule.shift_assignments.items():
            for nurse_id in assigned_nurse_ids:
                nurse = nurses[nurse_id]
                if nurse_id:
                    shifts_per_nurse[nurse].append(shift)

        total_cost = 0.0

        for shift, assigned_nurse_ids in schedule.shift_assignments.items():
            assigned_nurses = [n for n in nurses if n in assigned_nurse_ids]
            for nurse_id in assigned_nurses:
                nurse = nurses[nurse_id]
                if not nurse_id in nurse_shift_hours_state_tracker_per_nurse:
                    nurse_shift_hours_state_tracker_per_nurse[nurse_id] = NurseShiftHoursStateTracker(
                        nurse,
                        overtime_calculator
                    )

                nurse_shift_hr_tracker = nurse_shift_hours_state_tracker_per_nurse[nurse_id]

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

    @staticmethod
    def _calc_risk_metrics(
            shifts: List[Shift],
            schedule: Schedule,
            nurses: List[NurseProfile],
            shift_requirements: ShiftSpecificRequirements,
    ) -> RiskMetrics:
        """
        quantify non-financial risk.
        """

        regulatory_compliance_score_agg = 100.0
        staff_wellbeing_index_agg = 100.0

        for shift in shifts:
            assigned_nurse_ids = schedule.shift_assignments[shift]
            assigned_nurses = [n for n in nurses if n.employee_id in assigned_nurse_ids]
            rn_assigned = [n for n in assigned_nurses if n.role == NurseRole.RN]
            lpn_assigned = [n for n in assigned_nurses if n.role == NurseRole.LPN]
            cna_assigned = [n for n in assigned_nurses if n.role == NurseRole.CNA]
            # total_assigned = len(assigned_nurses)

            required_rn = shift_requirements.target_hprd_rn
            required_lpn = shift_requirements.target_hprd_lpn
            required_cna = shift_requirements.target_hprd_cna
            # required_total = shift_requirements.target_total_hprd

            rn_diff = len(rn_assigned) - required_rn
            lpn_diff = len(lpn_assigned) - required_lpn
            cna_diff = len(cna_assigned) - required_cna
            # total_diff = total_assigned - required_total

            regulatory_compliance_misses = 0.0

            if rn_diff < 0:
                regulatory_compliance_misses += rn_diff
            if lpn_diff < 0:
                regulatory_compliance_misses += lpn_diff
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
                            if pref.specific_day in [DayOfWeek.SATURDAY, DayOfWeek.SUNDAY]:
                                staff_wellbeing_misses -= 1

            regulatory_compliance_score_agg -= regulatory_compliance_misses
            staff_wellbeing_index_agg -= staff_wellbeing_misses

        return TestRunner.RiskMetrics(
            regulatory_compliance_score=max(0.0, regulatory_compliance_score_agg),
            staff_wellbeing_index=max(0.0, staff_wellbeing_index_agg)
        )
