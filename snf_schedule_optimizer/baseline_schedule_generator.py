import itertools
from typing import List, Dict, Any

from snf_schedule_optimizer.data_models import ResidentAcuity, Schedule, NurseProfile
from snf_schedule_optimizer.optimization_engine import Shift


class BaselineScheduleGenerator:
    def __init__(self) -> None:
        pass

    def generate_baseline_schedule(
            self,
            shifts: List[Shift],
            residents: List[ResidentAcuity],
            staff: List[NurseProfile],
    ) -> Schedule:
        """
        Generates a baseline schedule using a simple heuristic approach.
        placeholder implementation
        """
        shift_assignments: Dict[Shift, List[str]] = {}

        census = len(residents)

        staff_count = len(staff)
        for i, shift in enumerate(shifts):
            n_staff_to_assign = census
            for j in range(n_staff_to_assign):
                assigned_staff = staff[(i + j) % staff_count]
                shift_assignments.setdefault(shift, []).append(assigned_staff.employee_id)

        return Schedule(shift_assignments)
