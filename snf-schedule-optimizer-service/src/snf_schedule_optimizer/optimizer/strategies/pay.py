import pulp
import whenever
from pulp import LpProblem

from snf_schedule_optimizer.datetime_utils import is_weekend
from snf_schedule_optimizer.domain.payroll.calculations.shift_pay_processor import (
    ShiftPayProcessor,
)
from snf_schedule_optimizer.models import EmployeeIdType
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import (
    IIncentiveManager,
    ILaborBurdenCalculator,
    IPayModelStrategy,
    IScenarioDataProvider,
)


class ComprehensiveShiftCostStrategy(IPayModelStrategy):
    def __init__(
        self,
        burden_calc: ILaborBurdenCalculator,
        incentive_mgr: IIncentiveManager,
    ):
        self.burden_calc = burden_calc
        self.incentive_mgr = incentive_mgr

    async def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> list[pulp.LpAffineExpression]:
        terms = []

        for shift in data_provider.get_all_shifts():
            duration = (shift.shift_end_dt - shift.shift_start_dt).in_hours()
            config = data_provider.get_facility_config(shift.facility_id)
            nurses = await data_provider.get_nurses_for_shift(shift)

            for nurse in nurses:
                var = lp_holder.get_variable(
                    shift,
                    nurse.employee_id,
                )
                if not var:
                    continue

                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                comp_record = await data_provider.get_compensation_for_date(
                    nurse.employee_id,
                    shift.shift_start_dt.date(),
                )
                if not comp_record:
                    continue

                base_rate = float(comp_record.base_rate_effective)
                if base_rate is None:
                    continue

                base_wage = base_rate * duration

                diff_rate = 0.0
                if not shift.day_shift:
                    diff_rate += base_rate * max(
                        0.0, config.night_shift_multiplier - 1.0
                    )
                if is_weekend(shift.shift_start_dt.date().day_of_week()):
                    diff_rate += base_rate * max(0.0, config.weekend_multiplier - 1.0)
                shift_diff_cost = diff_rate * duration

                statutory, benefits = self.burden_calc.calculate_burden(
                    employee, base_wage + shift_diff_cost
                )

                incentives = self.incentive_mgr.calculate_incentives(
                    shift, employee, base_rate
                )

                total_cost = (
                    base_wage + shift_diff_cost + statutory + benefits + incentives
                )

                terms.append(var * total_cost)

        return terms

    async def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        pass

    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        pass


class WeeklyVolumePayStrategy(IPayModelStrategy):
    """
    Implements classic weekly overtime logic using Reg/OT buckets.
    """

    def __init__(
        self,
        shift_pay_processor: ShiftPayProcessor,
        threshold: float = 40.0,
    ):
        self.shift_pay_processor = shift_pay_processor
        self.threshold = threshold

    async def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        # Create Reg/OT buckets for everyone
        for emp in await data_provider.get_all_employees():
            lp_holder.add_pay_variables(emp.employee_id)

    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        unique_employees = lp_holder.get_all_employees()

        for emp_id in unique_employees:
            pay_vars = lp_holder.get_pay_variables(emp_id)
            if not pay_vars:
                continue

            worked_hours = await data_provider.get_accumulated_hours_for_pay_period(
                emp_id
            )
            remaining_cap = max(0.0, self.threshold - worked_hours)

            # Sum assigned hours
            assigned_hours = []
            for shift in data_provider.get_all_shifts():
                try:
                    var = lp_holder.get_variable(
                        shift,
                        emp_id,
                    )
                    if var is None:
                        continue
                    assigned_hours.append(var * shift.duration_hours)
                except KeyError:
                    pass

            if assigned_hours:
                # 1. Total = Reg + OT
                problem += (
                    pulp.lpSum(assigned_hours) == pay_vars["reg"] + pay_vars["ot"]
                )
                # 2. Reg Cap
                problem += pay_vars["reg"] <= remaining_cap

    async def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> list[pulp.LpAffineExpression]:
        terms = []

        # --- Part A: Shift-Specific Costs (Straight Time + Diffs + Incentives) ---
        shifts = data_provider.get_all_shifts()
        settings = data_provider.get_optimization_settings()
        for shift in shifts:
            config = data_provider.get_facility_config(shift.facility_id)
            nurses = await data_provider.get_nurses_for_shift(shift)

            for nurse in nurses:
                variable = lp_holder.get_variable(
                    shift,
                    nurse.employee_id,
                )
                if variable is None:
                    continue

                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if employee is None:
                    continue

                # Calculate "Straight Time" Cost
                # We pass 0.0 hours to force the processor to calculate this shift
                # as if it were the first shift of the week (no automatic OT).
                # The OT Buckets will handle the premium if this pushes them over.
                straight_time_breakdown = (
                    await self.shift_pay_processor.calculate_detailed_cost(
                        employee=employee,
                        shift=shift,
                        current_weekly_hours=0.0,
                        facility_config=config,
                        skip_overtime_computation=True,
                    )
                )

                # Sum up Base + Diffs + Burdens + Incentives
                # Note: We assume calculate_detailed_cost returns 0.0 for overtime_premium
                # because we passed 0.0 current hours and shift < threshold.
                shift_cost = (
                    straight_time_breakdown.base_wage
                    + straight_time_breakdown.shift_differentials
                    + straight_time_breakdown.incentive_bonuses
                    + straight_time_breakdown.statutory_burden
                    + straight_time_breakdown.benefits_burden
                )

                if settings.premium_weekend and shift.day_of_week in {
                    whenever.Weekday.SATURDAY,
                    whenever.Weekday.SUNDAY,
                }:
                    shift_cost += straight_time_breakdown.base_wage * max(
                        0.0, config.weekend_multiplier - 1.0
                    )

                if (
                    settings.premium_holiday
                    and shift.shift_start_dt.date().month == 1
                    and shift.shift_start_dt.date().day == 1
                ):
                    shift_cost += straight_time_breakdown.base_wage * 0.5

                terms.append(variable * shift_cost)

        # --- Part B: OT Premium Costs (The 0.5x kicker) ---

        # We need a reference date to look up the rate.
        # Using the start of the first shift in the window is standard practice.
        reference_date = data_provider.get_all_shifts()[0].shift_start_dt

        unique_employees = lp_holder.get_all_employees()

        for emp_id in unique_employees:
            pay_vars = lp_holder.get_pay_variables(emp_id)
            if not pay_vars:
                continue

            comp_record = await data_provider.get_compensation_for_date(
                emp_id,
                reference_date.date(),
            )
            if not comp_record:
                continue

            base_rate = float(comp_record.base_rate_effective)
            ot_multiplier = float(comp_record.ot_multiplier)

            ot_premium_rate = base_rate * (ot_multiplier - 1.0)

            terms.append(pay_vars["ot"] * ot_premium_rate)

        return terms


class BiWeeklyPayPeriodOTStrategy(IPayModelStrategy):
    def __init__(self, threshold: float = 80.0):
        self.threshold = threshold
        self._bi_ot_vars: dict[EmployeeIdType, pulp.LpVariable] = {}

    async def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        for emp in await data_provider.get_all_employees():
            var = pulp.LpVariable(
                f"BiWeekly_OT_Excess_{emp.employee_id}",
                lowBound=0,
                cat=pulp.LpContinuous,
            )
            self._bi_ot_vars[emp.employee_id] = var

    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        for emp_id, bi_var in self._bi_ot_vars.items():
            assigned_terms = []
            for shift in data_provider.get_all_shifts():
                var = lp_holder.get_variable(shift, emp_id)
                if var is not None:
                    assigned_terms.append(var * shift.duration_hours)

            if not assigned_terms:
                continue

            total_assigned = pulp.lpSum(assigned_terms)
            accumulated = await data_provider.get_accumulated_hours_for_pay_period(
                emp_id
            )
            total = total_assigned + accumulated

            weekly_vars = lp_holder.get_pay_variables(emp_id)
            weekly_ot_term: pulp.LpVariable | pulp.LpAffineExpression
            if weekly_vars is not None:
                weekly_ot_term = weekly_vars["ot"]
            else:
                weekly_ot_term = pulp.LpAffineExpression()

            problem += bi_var >= total - self.threshold - weekly_ot_term

    async def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> list[pulp.LpAffineExpression]:
        terms: list[pulp.LpAffineExpression] = []
        shifts = data_provider.get_all_shifts()
        if not shifts:
            return terms
        reference_date = shifts[0].shift_start_dt

        for emp_id, bi_var in self._bi_ot_vars.items():
            comp = await data_provider.get_compensation_for_date(
                emp_id, reference_date.date()
            )
            if not comp:
                continue
            base_rate = float(comp.base_rate_effective)
            ot_multiplier = float(comp.ot_multiplier)
            premium = base_rate * (ot_multiplier - 1.0)
            terms.append(bi_var * premium)

        return terms


class DailyOvertimePayStrategy(IPayModelStrategy):
    """
    Strategy for jurisdictions (e.g. California) where Overtime is calculated
    daily (per shift) rather than weekly.
    """

    def __init__(
        self,
        shift_pay_processor: ShiftPayProcessor,
    ) -> None:
        self.shift_pay_processor = shift_pay_processor

    async def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        # No buckets needed for daily OT! Costs are on the shifts themselves.
        pass

    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> None:
        # No complex linking constraints needed for daily OT
        pass

    async def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
    ) -> list[pulp.LpAffineExpression]:
        terms = []
        shifts = data_provider.get_all_shifts()
        for shift in shifts:
            # For Daily OT, "accumulated weekly hours" doesn't affect the Daily OT rate.
            # We pass 0.0 so the processor calculates purely based on the shift duration > 8h.
            # (Assuming the FacilityConfig passed has the 8h daily threshold configured).

            config = data_provider.get_facility_config(shift.facility_id)
            nurses = await data_provider.get_nurses_for_shift(shift)

            for nurse in nurses:
                var = lp_holder.get_variable(
                    shift,
                    nurse.employee_id,
                )
                if not var:
                    continue

                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                cost_breakdown = await self.shift_pay_processor.calculate_detailed_cost(
                    employee=employee,
                    shift=shift,
                    current_weekly_hours=0.0,  # Irrelevant for Daily Rule
                    facility_config=config,
                )

                terms.append(var * cost_breakdown.total_optimization_cost)

        return terms
