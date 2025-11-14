from snf_schedule_optimizer.data_models import *
from snf_schedule_optimizer.optimization_engine import (
    ScheduleOptimizer, PreferenceWeights, DynamicModelOutputs
)
from snf_schedule_optimizer.robustness_tests.scenario_generator import (
    generate_simulated_acuity,
    generate_simulated_nurses,
    SimulateFacilityScenario)
import polars as pl


class TestRunner:
    def run_comparison_scenario(
            self,
            stress_params: TimeSeriesStressTestParameters,
            facility_params: FacilityConfig
    ) -> Dict[str, Any]:
        """
        Runs a single scenario to generate both forward- and backward-looking data.
        """

        nurses = generate_simulated_nurses(
            SimulateFacilityScenario(
                cna_base_wage=18.0,
                agency_multiplier=2.2,
                turnover_rate=0.3
            )
        )

        # --- 1. Generate Stressed Input Data ---
        # Assuming generate_simulated_acuity returns some type representing residents
        stressed_residents: List[ResidentAcuity] = generate_simulated_acuity(stress_params)

        # --- 2. FORWARD-LOOKING: Generate Optimal Schedule (The Product) ---

        # We test the model with parameters that prioritize cost savings
        optimal_params: PreferenceWeights = PreferenceWeights(
            Night_Shift_Penalty_Weight=500.0,  # keep default or adjust as needed
            OT_Avoidance_Penalty=10.0,  # was cost_weight
            Team_Consistency_Penalty=1.0  # was fairness_weight
        )

        model_outputs = DynamicModelOutputs(
            turnover_risk_scores={},
            shift_call_out_forecast={},
            resident_acuity_stress={},
            team_compatibility_scores={}
        )

        # Assuming solve returns a dict representing the schedule
        optimized_schedule: Optional[Dict[str, float]] = ScheduleOptimizer.solve(
            nurses,
            stressed_residents,
            facility_params,
            optimal_params,
            model_outputs
        )

        if optimized_schedule is None:
            raise RuntimeError("Optimization failed to produce a schedule.")

        # --- 3. BACKWARD-LOOKING: Simulate Baseline & Compare ---

        # a) Simulate Cost of Optimal Schedule (What you achieved)
        optimal_cost: float = self._calculate_cost(optimized_schedule, nurses)

        # b) Simulate Cost of Baseline (What the facility usually does - heuristic/manual)
        baseline_schedule: Dict[Any, Any] = self._generate_baseline_schedule(stressed_residents)
        baseline_cost: float = self._calculate_cost(baseline_schedule, nurses)

        # c) Simulate Operational Risk
        optimal_risk_score: float = self._run_risk_simulation(optimized_schedule)
        baseline_risk_score: float = self._run_risk_simulation(baseline_schedule)

        # Calculate savings
        cost_savings_percent: float = 0.0
        if baseline_cost > 0:
            cost_savings_percent = (baseline_cost - optimal_cost) / baseline_cost * 100

        # Note: Return type is Dict[str, Any] as metrics can be floats, ints, or strings
        return {
            'Scenario_ID': f"Surge_{stress_params.admission_surge_factor}",
            'Baseline_Cost': baseline_cost,
            'Optimized_Cost': optimal_cost,
            'Cost_Savings_Percent': cost_savings_percent,
            'Baseline_Risk_Score': baseline_risk_score,
            'Optimized_Risk_Score': optimal_risk_score
        }

    # --- Structural Shells for Future Complexity ---

    def run_sensitivity_analysis(
            self,
            param_name: str,
            values: List[Any],
            default_values: dict[str, Any]
    ) -> pl.DataFrame:
        """
        Varies a single TimeSeriesParameters field (param_name) across provided values and
        runs comparison scenarios. Returns a Polars DataFrame of aggregated metrics.
        """
        if not values:
            return pl.DataFrame([])

        results: List[Dict[str, Any]] = []
        for value in values:
            # Build TimeSeriesParameters with the varied field; rely on defaults for others.
            try:
                stress_params = TimeSeriesStressTestParameters(**{param_name: value | default_values})
            except TypeError:
                # Fallback: instantiate default then setattr; raise if attribute invalid.
                stress_params = TimeSeriesStressTestParameters(**default_values)
                if not hasattr(stress_params, param_name):
                    raise ValueError(f"Unknown TimeSeriesParameters field: {param_name}")
                setattr(stress_params, param_name, value)

            scenario_metrics = self.run_comparison_scenario(
                stress_params,
                FacilityConfig(
                    facility_id="TEST_FACILITY_001",
                    target_hprd_rn=0.7,
                    max_consecutive_shifts=6,
                    base_cna_hprd_mandate=2.5,
                    shifts_per_day=3
                )
            )
            # Tag with varied parameter value
            scenario_metrics[param_name] = value
            results.append(scenario_metrics)

        # Order columns: parameter first, then metrics
        df = pl.DataFrame(results)
        if param_name in df.columns:
            cols = [param_name] + [c for c in df.columns if c != param_name]
            df = df.select(cols)
        return df

    @staticmethod
    def _generate_baseline_schedule(residents: Any) -> Dict[Any, Any]:
        """Mocks the facility's existing, often inefficient, manual scheduling heuristic."""
        # Simple mock implementation returning an empty schedule dict
        return {}

    @staticmethod
    def _calculate_cost(schedule: Dict[Any, Any], nurses: List[NurseProfile]) -> float:
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
    def _run_risk_simulation(schedule: Optional[Dict[str, float]]) -> float:
        """
        Structural shell for the DES to quantify non-financial risk.
        MOCK: Returns a high risk for the baseline schedule.
        """
        # MOCK: A simple risk proxy. Optimal schedule has lower risk score.
        risk_score: float = 10.0
        if not schedule:  # Baseline is mocked as an empty schedule for simplicity
            return risk_score * 3.0  # Higher risk for the baseline/inefficient schedule

        return risk_score
