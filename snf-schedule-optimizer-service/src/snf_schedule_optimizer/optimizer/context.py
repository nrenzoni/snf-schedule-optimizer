from dataclasses import dataclass

import numpy as np
import pulp
from pulp import LpVariable

from snf_schedule_optimizer.models import (
    FacilityConfig,
    HprdEnforcedRole,
    MinMandates,
    Shift,
)
from snf_schedule_optimizer.optimizer.lp_helpers import build_lp_variable_name


@dataclass(frozen=True)
class FacilityScenarioContext:
    """Grouping of inputs specific to a single facility for a scenario run."""

    facility_id: str
    shifts: list[Shift]
    config: FacilityConfig
    min_mandates: MinMandates | None = None
    # Future: Facility-specific acuity data, etc.


@dataclass(frozen=True)
class LpShiftKey:
    facility_id: str
    employee_id: str
    shift_id: str


class LpNurseShiftVariableHolder:
    def __init__(self) -> None:
        self._assignment_vars: dict[LpShiftKey, LpVariable] = {}

        # Key is Tuple: (employee_id, bucket_type) -> bucket_type is 'reg' or 'ot'
        self._pay_vars: dict[tuple[str, str], LpVariable] = {}

    def add_variable(
        self,
        facility_id: str,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable:
        key = LpShiftKey(facility_id, employee_id, shift_id)

        if key in self._assignment_vars:
            raise ValueError(
                f"Variable for Facility {facility_id}, Employee {employee_id}, Shift {shift_id} already exists."
            )

        # Include Facility ID in the variable name to ensure uniqueness in PuLP
        # will NEVER parse this string back.
        var_name = build_lp_variable_name(facility_id, employee_id, shift_id)

        var = LpVariable(var_name, cat=pulp.LpBinary)

        self._assignment_vars[key] = var
        return var

    def get_variable(
        self,
        facility_id: str,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable | None:
        return self._assignment_vars.get(LpShiftKey(facility_id, employee_id, shift_id))

    def add_pay_variables(self, employee_id: str) -> None:
        """Creates the bucket variables for Volume-based OT."""

        # Regular Hours
        reg_var = LpVariable(
            build_lp_variable_name("Pay", "Reg", employee_id),
            lowBound=0,
            cat=pulp.LpContinuous,
        )
        self._pay_vars[(employee_id, "reg")] = reg_var

        # OT Hours
        ot_var = LpVariable(
            build_lp_variable_name("Pay", "OT", employee_id),
            lowBound=0,
            cat=pulp.LpContinuous,
        )
        self._pay_vars[(employee_id, "ot")] = ot_var

    def get_pay_variables(self, employee_id: str) -> dict[str, LpVariable] | None:
        """Returns a dict {'reg': Var, 'ot': Var} for easy access."""
        reg = self._pay_vars.get((employee_id, "reg"))
        ot = self._pay_vars.get((employee_id, "ot"))

        if reg is not None and ot is not None:
            return {"reg": reg, "ot": ot}
        return None

    def get_all_assignments(self) -> dict[LpShiftKey, LpVariable]:
        """Expose the raw dictionary for efficient iteration during result extraction."""
        return self._assignment_vars

    def get_all_employees(self) -> set[str]:
        """Returns a set of all employee IDs with assignment variables."""
        # Unpack 3 keys: facility_id, employee_id, shift_id
        return set(var.employee_id for var in self._assignment_vars.keys())


class HprdShiftNurseRequirementHolder:
    """
    Stores the required HPRD-adjusted nurse hours per shift and role.
    """

    def __init__(
        self,
        shifts: list[str],  # shift_ids
        roles: list[HprdEnforcedRole],
    ):
        # self.values: np.ndarray[Any, np.dtype[np.float64]]  # Shape: (n_shifts, n_roles)
        self.values = np.zeros((len(shifts), len(roles) + 1))

        self.shifts = shifts  # shift_ids
        self.roles = roles

    def __setitem__(
        self,
        key: tuple[str, HprdEnforcedRole],
        value: float,
    ) -> None:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        self.values[shift_idx, role_idx] = value

    def __getitem__(
        self,
        key: tuple[str, HprdEnforcedRole],
    ) -> float:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        return float(self.values[shift_idx, role_idx])

    def add_total_req(self, shift: Shift, value: float) -> None:
        shift_idx = self.shifts.index(shift.shift_id)
        self.values[shift_idx, -1] += value

    def get_total_req(self, shift_str: str) -> float:
        shift_idx = self.shifts.index(shift_str)
        return float(self.values[shift_idx, -1])
