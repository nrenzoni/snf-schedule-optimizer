from snf_schedule_optimizer.baseline_schedule_generator import BaselineScheduleGenerator
from snf_schedule_optimizer.data_models import *
from snf_schedule_optimizer.optimization_engine import (
    ScheduleOptimizer, PreferenceWeights, MlModelOutputs, Shift, Schedule
)
from snf_schedule_optimizer.robustness_tests.scenario_generator import (
    generate_simulated_acuity,
    generate_simulated_nurses,
    SimulateFacilityScenarioParams)
import polars as pl

N_FORECAST_AHEAD_DAYS = 14


class TestRunner:
    def run_sensitivity_analysis(
            self,
            test_param_name: str,
            single_param_test_values: List[Any],
            param_default_values: dict[str, Any],
    ) -> pl.DataFrame:
        """
        Varies a single TimeSeriesParameters field (param_name) across provided values and
        runs comparison scenarios. Returns a Polars DataFrame of aggregated metrics.
        """
        if not single_param_test_values:
            return pl.DataFrame([])

        shifts = [
            Shift(
                shift_number=i,
                day_shift=(i % 3 != 0),
                day_of_week=DayOfWeek((i - 1) % 7 + 1),  # 1=Mon, 7=Sun
            )
            for i in range(1, N_FORECAST_AHEAD_DAYS + 1)
        ]

        min_mandates = [
            MinMandates(
                min_rn_hprd=0.7,
                min_lpn_hprd=0.75,
                min_cna_hprd=2.5,
                min_total_hprd=2.75,
                min_staff_per_shift_rn=1,
                min_staff_per_shift_lpn=1,
                min_staff_per_shift_cna=2
            )
        ]

        results: List[Dict[str, Any]] = []

        for value in single_param_test_values:
            # Build TimeSeriesParameters with the varied field; rely on defaults for others.
            try:
                stress_params = StressTestParameters(**{test_param_name: value | param_default_values})
            except TypeError:
                # Fallback: instantiate default then setattr; raise if attribute invalid.
                stress_params = StressTestParameters(**param_default_values)
                if not hasattr(stress_params, test_param_name):
                    raise ValueError(f"Unknown TimeSeriesParameters field: {test_param_name}")
                setattr(stress_params, test_param_name, value)

            requirements = ShiftSpecificRequirements(
                target_hprd_rn=1.0,
                target_hprd_lpn=1.0,
                target_hprd_cna=3.0,
                target_total_hprd=3.5
            )

            scenario_metrics = self.run_scenario(
                shifts,
                stress_params,
                FacilityConfig(
                    facility_id="TEST_FACILITY_001",
                    max_consecutive_shifts=6,
                    shifts_per_day=3
                ),
                min_mandates,
                requirements
            )

            # Tag with varied parameter value
            scenario_metrics[test_param_name] = value
            results.append(scenario_metrics)

        # Order columns: parameter first, then metrics
        df = pl.DataFrame(results)
        if test_param_name in df.columns:
            cols = [test_param_name] + [c for c in df.columns if c != test_param_name]
            df = df.select(cols)
        return df

    def run_scenario(
            self,
            shifts: List[Shift],
            stress_params: StressTestParameters,
            facility_params: FacilityConfig,
            min_mandates: List[MinMandates],
            shift_requirements: ShiftSpecificRequirements,
    ) -> Dict[str, Any]:
        """
        Runs a single scenario to generate both forward- and backward-looking data.
        """

        nurses = generate_simulated_nurses(
            SimulateFacilityScenarioParams(
                cna_base_wage=18.0,
                agency_multiplier=2.2,
                turnover_rate=0.3
            )
        )

        stressed_residents: List[ResidentAcuity] = generate_simulated_acuity(stress_params)

        # parameters prioritize cost savings
        user_scheduler_pref_weights: PreferenceWeights = PreferenceWeights(
            night_shift_penalty_weight=500.0,
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
            facility_params,
            min_mandates,
            user_scheduler_pref_weights,
            shift_requirements,
            model_outputs
        )

        if not optimized_schedule_res.success:
            raise RuntimeError("Optimization failed to produce a schedule.")

        optimal_schedule = optimized_schedule_res.optimal_schedule
        assert optimal_schedule is not None

        # --- 3. BACKWARD-LOOKING: Simulate Baseline & Compare ---

        # a) Simulate Cost of Optimal Schedule (What you achieved)
        optimal_cost: float = self._calculate_cost(optimal_schedule, nurses)

        # b) Simulate Cost of Baseline (What the facility usually does - heuristic/manual)
        # baseline_schedule: Dict[Any, Any] = self._generate_baseline_schedule(stressed_residents)
        baseline_schedule = BaselineScheduleGenerator().generate_baseline_schedule(
            stressed_residents,
            nurses,
            shifts
        )

        baseline_cost: float = self._calculate_cost(baseline_schedule, nurses)

        # c) Simulate Operational Risk
        optimal_risk_score: float = self._run_risk_simulation(optimal_schedule)
        baseline_risk_score: float = self._run_risk_simulation(baseline_schedule)

        # Calculate savings
        cost_savings_percent: float = 0.0
        if baseline_cost > 0:
            cost_savings_percent = (baseline_cost - optimal_cost) / baseline_cost * 100

        # Note: Return type is Dict[str, Any] as metrics can be floats, ints, or strings
        return {
            'Scenario_ID'         : f"Surge_{stress_params.admission_surge_factor}",
            'Baseline_Cost'       : baseline_cost,
            'Optimized_Cost'      : optimal_cost,
            'Cost_Savings_Percent': cost_savings_percent,
            'Baseline_Risk_Score' : baseline_risk_score,
            'Optimized_Risk_Score': optimal_risk_score
        }

    @staticmethod
    def _generate_baseline_schedule(residents: Any) -> Dict[Any, Any]:
        """Mocks the facility's existing, often inefficient, manual scheduling heuristic."""
        # Simple mock implementation returning an empty schedule dict
        return {}

    @staticmethod
    def _calculate_cost(schedule: Schedule, nurses: List[NurseProfile]) -> float:
        """
        Calculates the total dollar cost based on assignments and pay rates.
        MOCK: Returns a cost based on the number of nurses, simulating higher cost for baseline.
        """
        # A simple cost proxy for mocking purposes
        total_cost: float = len(nurses) * 8_000.0 * (1.1 if not schedule else 1.0)

        # If this were the baseline, we'd mock a higher cost
        if not schedule:  # Baseline is mocked as an empty schedule for simplicity
            return total_cost * 1.5

        return total_cost

    @staticmethod
    def _run_risk_simulation(schedule: Schedule) -> float:
        """
        Structural shell for the DES to quantify non-financial risk.
        MOCK: Returns a high risk for the baseline schedule.
        """
        # MOCK: A simple risk proxy. Optimal schedule has lower risk score.
        risk_score: float = 10.0
        if not schedule:  # Baseline is mocked as an empty schedule for simplicity
            return risk_score * 3.0  # Higher risk for the baseline/inefficient schedule

        return risk_score
