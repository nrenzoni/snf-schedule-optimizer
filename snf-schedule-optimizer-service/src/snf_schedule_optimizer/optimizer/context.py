from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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
    shifts: List[Shift]
    config: FacilityConfig
    min_mandates: MinMandates
    # Future: Facility-specific acuity data, etc.


class LpNurseShiftVariableHolder:
    def __init__(self) -> None:
        self.variables: Dict[str, LpVariable] = {}
        # Stores: employee_id -> {'reg': Var, 'ot': Var}
        self.pay_variables: Dict[str, Dict[str, LpVariable]] = {}

    def add_variable(
        self,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable:
        var_name = f"X__{employee_id}__{shift_id}"
        var = LpVariable(var_name, cat=pulp.LpBinary)
        self.variables[var_name] = var
        return var

    def get_variable(
        self,
        employee_id: str,
        shift_id: str,
    ) -> LpVariable:
        return self.variables[f"X__{employee_id}__{shift_id}"]

    def add_pay_variables(
        self,
        employee_id: str,
    ) -> None:
        """Creates the bucket variables for Volume-based OT."""
        self.pay_variables[employee_id] = {
            "reg": LpVariable(
                f"H_Reg__{employee_id}", lowBound=0, cat=pulp.LpContinuous
            ),
            "ot": LpVariable(f"H_OT__{employee_id}", lowBound=0, cat=pulp.LpContinuous),
        }

    def get_pay_variables(
        self,
        employee_id: str,
    ) -> Optional[Dict[str, LpVariable]]:
        return self.pay_variables.get(employee_id)


class HprdShiftNurseRequirementHolder:
    """
    Stores the required HPRD-adjusted nurse hours per shift and role.
    """

    def __init__(
        self,
        shifts: List[str],  # shift_ids
        roles: List[HprdEnforcedRole],
    ):
        # self.values: np.ndarray[Any, np.dtype[np.float64]]  # Shape: (n_shifts, n_roles)
        self.values = np.zeros((len(shifts), len(roles) + 1))

        self.shifts = shifts  # shift_ids
        self.roles = roles

    def __setitem__(
        self,
        key: Tuple[str, HprdEnforcedRole],
        value: float,
    ) -> None:  # (shift_id, NurseRole)
        shift_idx = self.shifts.index(key[0])
        role_idx = self.roles.index(key[1])
        self.values[shift_idx, role_idx] = value

    def __getitem__(
        self,
        key: Tuple[str, HprdEnforcedRole],
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
