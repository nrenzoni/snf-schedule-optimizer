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


@dataclass
class FacilityScenarioContext:
    """Grouping of inputs specific to a single facility for a scenario run."""

    facility_id: str
    shifts: list[Shift]
    config: FacilityConfig
    min_mandates: MinMandates | None = None
    # Future: Facility-specific acuity data, etc.


class LpNurseShiftVariableHolder:
    def __init__(self) -> None:
        # Key is Tuple: (employee_id, shift_id)
        self._assignment_vars: dict[tuple[str, str], LpVariable] = {}

        # Key is Tuple: (employee_id, bucket_type) -> bucket_type is 'reg' or 'ot'
        self._pay_vars: dict[tuple[str, str], LpVariable] = {}

    def add_variable(
        self,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable:
        # 1. Store using the Tuple (Robust)
        key = (employee_id, shift_id)

        # Create a safe name for the Solver
        # We sanitize the IDs just to ensure valid LP file syntax,
        # but we will NEVER parse this string back.
        safe_emp = self._sanitize(employee_id)
        safe_shift = self._sanitize(shift_id)
        var_name = f"X_{safe_emp}_{safe_shift}"

        var = LpVariable(var_name, cat=pulp.LpBinary)

        self._assignment_vars[key] = var
        return var

    def get_variable(
        self,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable | None:
        return self._assignment_vars.get((employee_id, shift_id))

    def add_pay_variables(self, employee_id: str) -> None:
        """Creates the bucket variables for Volume-based OT."""
        safe_emp = self._sanitize(employee_id)

        # Regular Hours
        reg_var = LpVariable(f"Pay_Reg_{safe_emp}", lowBound=0, cat=pulp.LpContinuous)
        self._pay_vars[(employee_id, "reg")] = reg_var

        # OT Hours
        ot_var = LpVariable(f"Pay_OT_{safe_emp}", lowBound=0, cat=pulp.LpContinuous)
        self._pay_vars[(employee_id, "ot")] = ot_var

    def get_pay_variables(self, employee_id: str) -> dict[str, LpVariable] | None:
        """Returns a dict {'reg': Var, 'ot': Var} for easy access."""
        reg = self._pay_vars.get((employee_id, "reg"))
        ot = self._pay_vars.get((employee_id, "ot"))

        if reg is not None and ot is not None:
            return {"reg": reg, "ot": ot}
        return None

    def get_all_assignments(self) -> dict[tuple[str, str], LpVariable]:
        """Expose the raw dictionary for efficient iteration during result extraction."""
        return self._assignment_vars

    def get_all_employees(self) -> set[str]:
        """Returns a set of all employee IDs with assignment variables."""
        return set(emp_id for emp_id, _ in self._assignment_vars.keys())

    @staticmethod
    def _sanitize(name: str) -> str:
        """Ensures IDs are clean for LP file formats (optional but recommended)."""
        return name.replace("-", "_").replace(" ", "_").replace("__", "_")


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
