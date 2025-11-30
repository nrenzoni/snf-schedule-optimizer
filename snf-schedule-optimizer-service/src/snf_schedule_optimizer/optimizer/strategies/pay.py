from typing import Any, List

import pulp
from pulp import LpProblem

from snf_schedule_optimizer.datetime_utils import is_weekend
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
        # nurse_retriever: INurseRetriever,
    ):
        self.burden_calc = burden_calc
        self.incentive_mgr = incentive_mgr
        # self.nurse_retriever = nurse_retriever

    def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> List[pulp.LpAffineExpression]:
        terms = []

        for shift in data_provider.get_all_shifts():
            duration = (shift.shift_end_dt - shift.shift_start_dt).total_hours()
            nurses = data_provider.get_nurses_for_shift(shift)

            for nurse in nurses:
                var = lp_holder.get_variable(nurse.employee_id, shift.shift_id)

                employee = data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                # --- 1. Base Calculations ---
                comp_record = (
                    data_provider.get_compensation_service().get_record_for_date(
                        nurse.employee_id, shift.shift_start_dt
                    )
                )
                if not comp_record:
                    continue  # No compensation record found

                base_rate = comp_record.base_rate_effective
                if base_rate is None:
                    continue

                base_wage = base_rate * duration

                # --- 2. Shift Differentials (Shift Dependent) ---
                diff_rate = 0.0
                if not shift.day_shift:
                    diff_rate += 2.00
                if is_weekend(shift.shift_start_dt.day_of_week):
                    diff_rate += 1.50
                shift_diff_cost = diff_rate * duration

                employee = data_provider.get_employee_by_id(nurse.employee_id)
                if not employee:
                    continue

                # --- 3. Burden (Taxes & Benefits) ---
                # We burden the Base + Diff (usually taxes apply to diffs too)

                statutory, benefits = self.burden_calc.calculate_burden(
                    employee, base_wage + shift_diff_cost
                )

                # --- 4. Incentives (Holidays, Pickups) ---
                incentives = self.incentive_mgr.calculate_incentives(
                    shift, employee, base_rate
                )

                # --- 5. Total Decision Cost ---
                total_cost = (
                    base_wage + shift_diff_cost + statutory + benefits + incentives
                )

                terms.append(var * total_cost)

        return terms

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        pass

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        pass


class WeeklyVolumePayStrategy(IPayModelStrategy):
    """
    Implements classic weekly overtime logic using Reg/OT buckets.
    """

    def __init__(
        self,
        threshold: float = 40.0,
    ):
        self.threshold = threshold

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        # Create Reg/OT buckets for everyone
        for emp in data_provider.get_all_employees():
            lp_holder.add_pay_variables(emp.employee_id)

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        unique_employees = set(lp_holder.pay_variables.keys())

        for emp_id in unique_employees:
            pay_vars = lp_holder.get_pay_variables(emp_id)
            if not pay_vars:
                continue
            worked_hours = data_provider.get_accumulated_hours_for_pay_period(emp_id)
            remaining_cap = max(0.0, self.threshold - worked_hours)

            # Sum assigned hours
            assigned_hours = []
            for shift in data_provider.get_all_shifts():
                try:
                    var = lp_holder.get_variable(emp_id, shift.shift_id)
                    duration = (shift.shift_end_dt - shift.shift_start_dt).total_hours()
                    assigned_hours.append(var * duration)
                except KeyError:
                    pass

            if assigned_hours:
                # 1. Total = Reg + OT
                problem += (
                    pulp.lpSum(assigned_hours) == pay_vars["reg"] + pay_vars["ot"]
                )
                # 2. Reg Cap
                problem += pay_vars["reg"] <= remaining_cap

    def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> List[pulp.LpAffineExpression]:
        terms = []
        unique_employees = set(lp_holder.pay_variables.keys())

        # We need a reference date to look up the rate.
        # Using the start of the first shift in the window is standard practice.
        reference_date = data_provider.get_all_shifts()[0].shift_start_dt

        for emp_id in unique_employees:
            pay_vars = lp_holder.get_pay_variables(emp_id)

            if not pay_vars:
                continue

            comp_record = data_provider.get_compensation_service().get_record_for_date(
                emp_id, reference_date
            )
            if not comp_record:
                continue

            # Handle case where no record exists (e.g. inactive employee)
            # Assuming the property on StaffCompensationRecord is 'base_hourly_rate'

            base_rate = comp_record.base_rate_effective

            # Buckets carry the cost
            terms.append(pay_vars["reg"] * base_rate)
            terms.append(pay_vars["ot"] * (base_rate * 1.5))

        return terms


class DailyOvertimePayStrategy(IPayModelStrategy):
    def __init__(
        self,
        # staff_comp_service: IStaffCompensationService,
        # nurse_retriever: INurseRetriever,
    ) -> None:
        # self.comp_service = staff_comp_service
        # self.nurse_retriever = nurse_retriever
        pass

    def create_variables(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        # No buckets needed for daily OT! Costs are on the shifts themselves.
        pass

    def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> None:
        # No complex linking constraints needed for daily OT
        pass

    def get_objective_terms(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: "IScenarioDataProvider",
    ) -> List[pulp.LpAffineExpression]:
        terms = []
        for shift in data_provider.get_all_shifts():
            duration = (shift.shift_end_dt - shift.shift_start_dt).total_hours()
            # Calculate cost ONCE here (deterministic)
            is_ot_shift = duration > 8.0

            nurses = data_provider.get_nurses_for_shift(shift)
            for nurse in nurses:
                comp_record = (
                    data_provider.get_compensation_service().get_record_for_date(
                        nurse.employee_id, shift.shift_start_dt
                    )
                )
                if not comp_record:
                    continue

                base_rate = comp_record.base_rate_effective
                if base_rate is None:
                    continue

                var = lp_holder.get_variable(nurse.employee_id, shift.shift_id)

                if is_ot_shift:
                    reg_hours = 8.0
                    ot_hours = duration - 8.0
                    cost = (reg_hours * base_rate) + (ot_hours * base_rate * 1.5)
                else:
                    cost = duration * base_rate

                terms.append(var * cost)
        return terms
