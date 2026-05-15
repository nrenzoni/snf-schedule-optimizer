from typing import Any, cast

import pulp
import whenever
from pulp import LpProblem

from snf_schedule_optimizer.models import (
    DomainPrimaryKeyType,
    EmploymentClassification,
    NurseProfile,
    Shift,
)
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder
from snf_schedule_optimizer.optimizer.interfaces import (
    IFacilityScopedConstraintStrategy,
    INurseHardBlockChecker,
    IScenarioDataProvider,
)
from snf_schedule_optimizer.optimizer.lp_helpers import build_lp_variable_name
from snf_schedule_optimizer.optimizer.models import (
    InfeasibilityReason,
    InfeasibilityReasonResult,
)


class HprdStaffingConstraintStrategy(IFacilityScopedConstraintStrategy):
    def __init__(
        self,
        hard_block_checker: INurseHardBlockChecker,
    ):
        self.hard_block_checker = hard_block_checker

    async def apply_constraints(
        self,
        problem: pulp.LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        # todo: Add infeasibility checks (e.g., no available nurses for a required role)

        requirements_holder = await data_provider.get_hprd_requirements_for_facility(
            facility_id
        )
        shifts = data_provider.get_shifts_for_facility(facility_id)

        # "For every shift, sum of assigned nurses >= Required HPRD count"
        for shift in shifts:
            # Get requirements (e.g., {RN: 2.5, CNA: 10.0})
            # This assumes your HPRD holder logic is accessible or pre-calculated
            # For simplicity, let's assume we iterate roles:
            for role in requirements_holder.roles:
                required_count = requirements_holder[shift.shift_id, role]

                if required_count <= 0:
                    continue

                available_vars = []
                nurses = await data_provider.get_nurses_for_shift(shift)

                for nurse in nurses:
                    # Filter by Hard Blocks (Time off, etc.)
                    # Note: We enforce blocks by NOT adding the variable to the sum,
                    # OR by explicitly adding x = 0 constraint.
                    # Explicit constraint is safer for transparency.
                    lp_var = lp_holder.get_variable(
                        shift,
                        nurse.employee_id,
                    )

                    if lp_var is None:
                        continue

                    if self.hard_block_checker.check(nurse, shift):
                        # HARD BLOCK: Force variable to 0
                        problem += (
                            lp_var == 0,
                            build_lp_variable_name(
                                "HardBlock", nurse.employee_id, shift.shift_id
                            ),
                        )
                        continue

                    # Filter by Role
                    employee = await data_provider.get_employee_by_id(nurse.employee_id)
                    if not employee:
                        continue  # todo: should this be an error?

                    if employee.job_title != role.value:
                        continue

                    # Available: Add to the pool
                    available_vars.append(lp_var)

                if len(available_vars) == 0:
                    return InfeasibilityReasonResult(
                        reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                        details=f"No available nurses for role {role.value} in shift {shift.shift_id} at facility {facility_id}.",
                    )

                # Add the HPRD Sum Constraint
                problem += (
                    pulp.lpSum(available_vars) >= required_count,
                    build_lp_variable_name(
                        "MinStaff", shift.facility_id, shift.shift_id, role.value
                    ),
                )

            total_required = requirements_holder.get_total_req(shift.shift_id)
            if total_required <= 0:
                continue

            total_available_vars = []
            for nurse in await data_provider.get_nurses_for_shift(shift):
                lp_var = lp_holder.get_variable(shift, nurse.employee_id)
                if lp_var is None or self.hard_block_checker.check(nurse, shift):
                    continue
                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if employee is None:
                    continue
                if employee.job_title in {
                    role.value for role in requirements_holder.roles
                }:
                    total_available_vars.append(lp_var)

            if len(total_available_vars) == 0:
                return InfeasibilityReasonResult(
                    reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                    details=f"No available direct-care nurses in shift {shift.shift_id} at facility {facility_id}.",
                )

            problem += (
                pulp.lpSum(total_available_vars) >= total_required,
                build_lp_variable_name(
                    "MinStaffTotal", shift.facility_id, shift.shift_id
                ),
            )

        return None


class ConsecutiveShiftFatigueStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        shifts = sorted(
            data_provider.get_shifts_for_facility(facility_id),
            key=lambda shift: shift.shift_start_dt,
        )
        if not shifts:
            return None

        min_rest_hours_val: float = (
            data_provider.get_optimization_settings().min_rest_period
        )
        config = data_provider.get_facility_config(facility_id)
        circadian_rest = config.min_circadian_rest_after_night if config else 11.0
        employee_states = await data_provider.get_employee_states()

        def _is_night_shift(s: Shift) -> bool:
            return not s.day_shift

        def _is_day_shift(s: Shift) -> bool:
            start_hour = s.shift_start_dt.time().hour
            return start_hour < 12

        def _get_rest_hours(s1: Shift, s2: Shift) -> float:
            if _is_night_shift(s1) and _is_day_shift(s2):
                return circadian_rest
            return min_rest_hours_val

        def _is_night_shift_type(shift_type: str | None) -> bool:
            return shift_type is not None and shift_type.lower() == "night"

        # 1. Rest constraints between decision-horizon shifts (existing logic)
        for i in range(len(shifts) - 1):
            for j in range(i + 1, len(shifts)):
                s1, s2 = shifts[i], shifts[j]
                if s2.shift_start_dt <= s1.shift_start_dt:
                    continue
                gap = (s2.shift_start_dt - s1.shift_end_dt).in_hours()
                rest_needed = _get_rest_hours(s1, s2)
                if gap >= rest_needed:
                    break

                nurses_s1 = {
                    n.employee_id for n in await data_provider.get_nurses_for_shift(s1)
                }
                nurses_s2 = {
                    n.employee_id for n in await data_provider.get_nurses_for_shift(s2)
                }
                common = nurses_s1.intersection(nurses_s2)

                for emp_id in common:
                    v1 = lp_holder.get_variable(s1, emp_id)
                    v2 = lp_holder.get_variable(s2, emp_id)
                    if v1 is None or v2 is None:
                        continue
                    problem += (
                        v1 + v2 <= 1,
                        f"Fatigue_{facility_id}_{emp_id}_{s1.shift_id}_{s2.shift_id}",
                    )

        # 2. History-aware rest: block early decision shifts if employee worked recently
        if shifts:
            first_shift_start = shifts[0].shift_start_dt
            for emp_id, state in employee_states.items():
                if state.last_shift_end is None:
                    continue
                try:
                    last_end_dt = whenever.ZonedDateTime.parse_common_iso(
                        state.last_shift_end
                    )
                except Exception:
                    continue
                rest_gap = (first_shift_start - last_end_dt).in_hours()

                effective_rest: float = min_rest_hours_val
                if _is_night_shift_type(state.last_shift_type) and _is_day_shift(
                    shifts[0]
                ):
                    effective_rest = circadian_rest

                if rest_gap >= effective_rest:
                    continue

                for shift in shifts:
                    gap = (shift.shift_start_dt - last_end_dt).in_hours()
                    need_rest = effective_rest
                    if _is_night_shift_type(state.last_shift_type) and _is_day_shift(
                        shift
                    ):
                        need_rest = circadian_rest
                    if gap >= need_rest:
                        continue
                    v = lp_holder.get_variable(shift, emp_id)
                    if v is None:
                        continue
                    problem += (
                        v == 0,
                        f"HistoryRest_{facility_id}_{emp_id}_{shift.shift_id}",
                    )

        return None


class ConsecutiveDaysLimitConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        config = data_provider.get_facility_config(facility_id)
        max_days = config.max_consecutive_work_days
        if max_days <= 0:
            return None

        employee_states = await data_provider.get_employee_states()
        shifts = data_provider.get_shifts_for_facility(facility_id)

        for emp_id, state in employee_states.items():
            if state.consecutive_days_worked >= max_days:
                for shift in shifts:
                    v = lp_holder.get_variable(shift, emp_id)
                    if v is None:
                        continue
                    problem += (
                        v == 0,
                        f"ConsecDaysCap_{facility_id}_{emp_id}_{shift.shift_id}",
                    )

        return None


class MaxShiftLengthConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        max_shift_length = data_provider.get_optimization_settings().max_shift_length
        for shift in data_provider.get_shifts_for_facility(facility_id):
            if shift.duration_hours <= max_shift_length:
                continue

            for nurse in await data_provider.get_nurses_for_shift(shift):
                lp_var = lp_holder.get_variable(shift, nurse.employee_id)
                if lp_var is None:
                    continue
                problem += (
                    lp_var == 0,
                    build_lp_variable_name(
                        "MaxShiftLength",
                        facility_id,
                        shift.shift_id,
                        nurse.employee_id,
                    ),
                )
        return None


class MaxWeeklyHoursConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        nurses_by_id = {}
        for shift in data_provider.get_shifts_for_facility(facility_id):
            for nurse in await data_provider.get_nurses_for_shift(shift):
                nurses_by_id[nurse.employee_id] = nurse

        for emp_id, nurse in nurses_by_id.items():
            worked_hours = await data_provider.get_accumulated_hours_for_pay_period(
                emp_id
            )
            remaining_capacity = nurse.available_hours_weekly - worked_hours
            if remaining_capacity < 0:
                return InfeasibilityReasonResult(
                    reason=InfeasibilityReason.OTHER,
                    details=(
                        f"Employee {emp_id} already exceeds weekly capacity before optimization."
                    ),
                )

            assigned_hours = []
            for shift in data_provider.get_shifts_for_facility(facility_id):
                lp_var = lp_holder.get_variable(shift, emp_id)
                if lp_var is not None:
                    assigned_hours.append(lp_var * shift.duration_hours)

            if assigned_hours:
                problem += (
                    pulp.lpSum(assigned_hours) <= remaining_capacity,
                    build_lp_variable_name("MaxWeeklyHours", facility_id, emp_id),
                )

        return None


class NurseShiftCountLimitStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        config = data_provider.get_facility_config(facility_id)
        shifts = data_provider.get_shifts_for_facility(facility_id)
        if not shifts:
            return None

        max_nights = config.max_night_shifts_per_month
        max_weekends = config.max_weekend_shifts_per_month

        if max_nights is None and max_weekends is None:
            return None

        nurses_by_id: dict[DomainPrimaryKeyType, NurseProfile] = {}
        for shift in shifts:
            for nurse in await data_provider.get_nurses_for_shift(shift):
                nurses_by_id[nurse.employee_id] = nurse

        for emp_id in nurses_by_id:
            night_vars = []
            weekend_vars = []
            for shift in shifts:
                v = lp_holder.get_variable(shift, emp_id)
                if v is None:
                    continue
                if not shift.day_shift and max_nights is not None:
                    night_vars.append(v)
                if shift.day_of_week.value >= 6 and max_weekends is not None:
                    weekend_vars.append(v)

            if night_vars and max_nights is not None and max_nights > 0:
                problem += (
                    pulp.lpSum(night_vars) <= max_nights,
                    build_lp_variable_name("MaxNightShifts", facility_id, emp_id),
                )
            if weekend_vars and max_weekends is not None and max_weekends > 0:
                problem += (
                    pulp.lpSum(weekend_vars) <= max_weekends,
                    build_lp_variable_name("MaxWeekendShifts", facility_id, emp_id),
                )

        return None


class ConsecutiveRnCoverageConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        shifts = sorted(
            data_provider.get_shifts_for_facility(facility_id),
            key=lambda s: s.shift_start_dt,
        )
        for i in range(len(shifts) - 1):
            s1, s2 = shifts[i], shifts[i + 1]
            if s1.shift_start_dt.date() != s2.shift_start_dt.date():
                continue
            gap = (s2.shift_start_dt - s1.shift_end_dt).in_hours()
            if gap > 0.5:
                continue

            rn_vars = []
            for s in (s1, s2):
                for nurse in await data_provider.get_nurses_for_shift(s):
                    employee = await data_provider.get_employee_by_id(nurse.employee_id)
                    if not employee or employee.job_title != "RN":
                        continue
                    v = lp_holder.get_variable(s, nurse.employee_id)
                    if v is not None:
                        rn_vars.append(v)

            if rn_vars:
                problem += (
                    pulp.lpSum(rn_vars) >= 1,
                    f"ConsecRN_{facility_id}_{s1.shift_id}_{s2.shift_id}",
                )
        return None


class LicensedNursePerShiftConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        shifts = data_provider.get_shifts_for_facility(facility_id)
        for shift in shifts:
            licensed_vars = []
            for nurse in await data_provider.get_nurses_for_shift(shift):
                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if not employee or employee.job_title not in {"RN", "LPN"}:
                    continue
                v = lp_holder.get_variable(shift, nurse.employee_id)
                if v is not None:
                    licensed_vars.append(v)

            if not licensed_vars:
                return InfeasibilityReasonResult(
                    reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                    details=f"No licensed nurse (RN/LPN) for shift {shift.shift_id} at facility {facility_id}",
                )

            problem += (
                pulp.lpSum(licensed_vars) >= 1,
                f"Licensed247_{facility_id}_{shift.shift_id}",
            )
        return None


class UnitMinimumStaffingConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        context = data_provider.get_facility_context(facility_id)
        unit_minimums = context.unit_minimums
        if not unit_minimums:
            return None

        shifts = data_provider.get_shifts_for_facility(facility_id)
        for shift in shifts:
            for unit_id, role_to_minimum in unit_minimums.items():
                for role, minimum_count in role_to_minimum.items():
                    if minimum_count <= 0:
                        continue
                    eligible_vars = []
                    for nurse in await data_provider.get_nurses_for_shift(shift):
                        if nurse.primary_unit_id != unit_id:
                            continue
                        employee = await data_provider.get_employee_by_id(
                            nurse.employee_id
                        )
                        if not employee or employee.job_title != role.value:
                            continue
                        lp_var = lp_holder.get_variable(shift, nurse.employee_id)
                        if lp_var is not None:
                            eligible_vars.append(lp_var)
                    if not eligible_vars:
                        return InfeasibilityReasonResult(
                            reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                            details=f"No eligible nurse for role {role.value} in unit {unit_id} shift {shift.shift_id} at facility {facility_id}",
                        )
                    problem += (
                        pulp.lpSum(eligible_vars) >= minimum_count,
                        build_lp_variable_name(
                            "UnitMin",
                            facility_id,
                            unit_id,
                            shift.shift_id,
                            role.value,
                        ),
                    )
        return None


class EmploymentClassificationConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        shifts = data_provider.get_shifts_for_facility(facility_id)
        config = data_provider.get_facility_config(facility_id)

        nurses_by_id: dict[
            DomainPrimaryKeyType, tuple[NurseProfile, EmploymentClassification]
        ] = {}
        for shift in shifts:
            for nurse in await data_provider.get_nurses_for_shift(shift):
                if nurse.employee_id not in nurses_by_id:
                    employee = await data_provider.get_employee_by_id(nurse.employee_id)
                    if employee:
                        nurses_by_id[nurse.employee_id] = (
                            nurse,
                            employee.classification,
                        )

        for emp_id, (nurse, classification) in nurses_by_id.items():
            max_hours = nurse.available_hours_weekly
            if classification == EmploymentClassification.PART_TIME:
                max_hours *= config.part_time_hour_fraction

            assigned_hours = []
            for shift in shifts:
                lp_var = lp_holder.get_variable(shift, emp_id)
                if lp_var is not None:
                    assigned_hours.append(lp_var * shift.duration_hours)

            if assigned_hours:
                problem += (
                    pulp.lpSum(assigned_hours) <= max_hours,
                    build_lp_variable_name(
                        "EmpClassCap", facility_id, emp_id, classification.value
                    ),
                )
        return None


class PdpmCategoryConstraintStrategy(IFacilityScopedConstraintStrategy):
    def __init__(
        self,
        resident_acuity_retriever: Any = None,
    ):
        self._resident_acuity_retriever = resident_acuity_retriever

    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        config = data_provider.get_facility_config(facility_id)
        pdpm_ratios = config.pdpm_category_ratios
        if not pdpm_ratios:
            return None

        shifts = data_provider.get_shifts_for_facility(facility_id)

        category_resident_counts = self._compute_pdpm_category_counts(
            data_provider, facility_id
        )

        for shift in shifts:
            for category, role_to_ratio in pdpm_ratios.items():
                resident_count = category_resident_counts.get(category, 0)
                if resident_count == 0:
                    continue
                for role, ratio in role_to_ratio.items():
                    required_nurses = _ceil_nonzero(resident_count * ratio)
                    if required_nurses <= 0:
                        continue
                    eligible_vars = []
                    for nurse in await data_provider.get_nurses_for_shift(shift):
                        employee = await data_provider.get_employee_by_id(
                            nurse.employee_id
                        )
                        if not employee or employee.job_title != role.value:
                            continue
                        lp_var = lp_holder.get_variable(shift, nurse.employee_id)
                        if lp_var is not None:
                            eligible_vars.append(lp_var)
                    if not eligible_vars:
                        return InfeasibilityReasonResult(
                            reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                            details=f"No eligible nurse for PDPM category {category} role {role.value} in shift {shift.shift_id} at facility {facility_id}",
                        )
                    problem += (
                        pulp.lpSum(eligible_vars) >= required_nurses,
                        build_lp_variable_name(
                            "PdpmCat",
                            facility_id,
                            shift.shift_id,
                            category,
                            role.value,
                        ),
                    )
        return None

    def _compute_pdpm_category_counts(
        self,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> dict[str, int]:
        if self._resident_acuity_retriever is not None:
            try:
                func = getattr(
                    self._resident_acuity_retriever,
                    "get_pdpm_category_counts",
                    None,
                )
                if func is not None:
                    return cast(dict[str, int], func(facility_id))
            except Exception:
                pass
        return {}


class FloatLimitConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        ctx = data_provider.get_facility_context(facility_id)
        if (
            ctx.hr_config is None
            or ctx.hr_config.max_floating_assignments_per_month is None
        ):
            return None

        max_floats = ctx.hr_config.max_floating_assignments_per_month
        if max_floats <= 0:
            return None

        shifts = data_provider.get_shifts_for_facility(facility_id)
        if not shifts:
            return None

        nurses_by_id: dict[DomainPrimaryKeyType, NurseProfile] = {}
        for shift in shifts:
            for nurse in await data_provider.get_nurses_for_shift(shift):
                nurses_by_id[nurse.employee_id] = nurse

        for emp_id, nurse in nurses_by_id.items():
            if nurse.primary_unit_id is None:
                continue
            float_vars = []
            for shift in shifts:
                if shift.unit_id is None or shift.unit_id == nurse.primary_unit_id:
                    continue
                v = lp_holder.get_variable(shift, emp_id)
                if v is not None:
                    float_vars.append(v)
            if float_vars and max_floats > 0:
                problem += (
                    pulp.lpSum(float_vars) <= max_floats,
                    build_lp_variable_name("FloatLimit", facility_id, emp_id),
                )
        return None


def _ceil_nonzero(value: float) -> int:
    if value <= 0:
        return 0
    import math

    return max(1, math.ceil(value))


class PreceptorRatioConstraintStrategy(IFacilityScopedConstraintStrategy):
    async def apply_constraints(
        self,
        problem: LpProblem,
        lp_holder: LpNurseShiftVariableHolder,
        data_provider: IScenarioDataProvider,
        facility_id: DomainPrimaryKeyType,
    ) -> InfeasibilityReasonResult | None:
        config = data_provider.get_facility_config(facility_id)
        max_new = config.max_new_grads_per_preceptor
        shifts = data_provider.get_shifts_for_facility(facility_id)

        nurses_by_id: dict[DomainPrimaryKeyType, NurseProfile] = {}
        for shift in shifts:
            for nurse in await data_provider.get_nurses_for_shift(shift):
                nurses_by_id[nurse.employee_id] = nurse

        for shift in shifts:
            new_grad_vars = []
            preceptor_vars = []
            charge_nurse_vars = []

            for nurse in await data_provider.get_nurses_for_shift(shift):
                v = lp_holder.get_variable(shift, nurse.employee_id)
                if v is None:
                    continue

                employee = await data_provider.get_employee_by_id(nurse.employee_id)
                if employee is None:
                    continue

                if employee.classification == EmploymentClassification.PRN:
                    new_grad_vars.append(v)
                else:
                    hire_dt = whenever.ZonedDateTime(
                        employee.hire_date.year,
                        employee.hire_date.month,
                        employee.hire_date.day,
                        0,
                        tz=shift.shift_start_dt.tz,
                    )
                    shift_dt = whenever.ZonedDateTime(
                        shift.shift_start_dt.date().year,
                        shift.shift_start_dt.date().month,
                        shift.shift_start_dt.date().day,
                        0,
                        tz=shift.shift_start_dt.tz,
                    )
                    hire_delta_days = (shift_dt - hire_dt).in_hours() / 24.0
                    if hire_delta_days <= 90:
                        new_grad_vars.append(v)

                if nurse.is_preceptor:
                    preceptor_vars.append(v)

                if nurse.is_charge_nurse:
                    charge_nurse_vars.append(v)

            if new_grad_vars and preceptor_vars:
                problem += (
                    pulp.lpSum(preceptor_vars) * max_new >= pulp.lpSum(new_grad_vars),
                    f"PreceptorRatio_{facility_id}_{shift.shift_id}",
                )
            elif new_grad_vars and not preceptor_vars:
                return InfeasibilityReasonResult(
                    reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                    details=f"No preceptor available for {len(new_grad_vars)} new grads in shift {shift.shift_id} at facility {facility_id}",
                )

            if config.require_charge_nurse_per_shift:
                if not charge_nurse_vars:
                    return InfeasibilityReasonResult(
                        reason=InfeasibilityReason.NO_AVAILABLE_NURSES,
                        details=f"No charge nurse available for shift {shift.shift_id} at facility {facility_id}",
                    )
                problem += (
                    pulp.lpSum(charge_nurse_vars) >= 1,
                    f"ChargeNurse_{facility_id}_{shift.shift_id}",
                )

        return None
