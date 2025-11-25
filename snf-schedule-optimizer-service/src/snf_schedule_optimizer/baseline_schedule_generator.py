from typing import Dict, List

from snf_schedule_optimizer.models import Schedule
from snf_schedule_optimizer.persistence.nurse_retrievers import INurseRetriever
from snf_schedule_optimizer.optimization_engine import Shift
from snf_schedule_optimizer.resident_acuity_retrievers import IResidentAcuityPerShiftRetriever


class BaselineScheduleGenerator:
    def __init__(
            self,
            resident_acuity_retriever: IResidentAcuityPerShiftRetriever,
            nurse_retriever: INurseRetriever,
    ) -> None:
        self.resident_acuity_retriever = resident_acuity_retriever
        self.nurse_retriever = nurse_retriever

    def generate_baseline_schedule(
            self,
            shifts: List[Shift],
    ) -> Schedule:
        """
        Generates a baseline schedule using a simple heuristic approach.
        placeholder implementation
        """
        shift_assignments: Dict[str, List[str]] = {}

        for i, shift in enumerate(shifts):
            nurses = self.nurse_retriever.get_nurses(shift)
            staff_count = len(nurses)
            curr_shift_residents_acuity = self.resident_acuity_retriever.get_resident_acuity_list(shift)
            census = len(curr_shift_residents_acuity)
            n_staff_to_assign = census
            for j in range(n_staff_to_assign):
                assigned_staff = nurses[(i + j) % staff_count]
                shift_assignments.setdefault(shift.shift_id, []).append(assigned_staff.employee_id)

        return Schedule(shift_assignments)
