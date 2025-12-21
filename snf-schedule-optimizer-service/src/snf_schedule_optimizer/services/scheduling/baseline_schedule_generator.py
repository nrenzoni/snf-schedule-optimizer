from snf_schedule_optimizer.models import (
    Schedule,
    Shift,
    ShiftAssignmentsType,
)
from snf_schedule_optimizer.persistence.nurse_retrievers import INurseRetriever
from snf_schedule_optimizer.resident_acuity_retrievers import (
    IResidentAcuityPerShiftRetriever,
)


class BaselineScheduleGenerator:
    def __init__(
        self,
        resident_acuity_retriever: IResidentAcuityPerShiftRetriever,
        nurse_retriever: INurseRetriever,
    ) -> None:
        self.resident_acuity_retriever = resident_acuity_retriever
        self.nurse_retriever = nurse_retriever

    async def generate_baseline_schedule(
        self,
        shifts: list[Shift],
    ) -> Schedule:
        """
        Generates a baseline schedule using a simple heuristic approach.
        placeholder implementation
        """
        if len(shifts) == 0:
            raise ValueError("No shifts provided for baseline schedule generation.")

        shift_assignments: ShiftAssignmentsType = {}

        for i, shift in enumerate(shifts):
            nurses = await self.nurse_retriever.get_nurses(shift)
            staff_count = len(nurses)
            curr_shift_residents_acuity = (
                self.resident_acuity_retriever.get_resident_acuity_list(shift)
            )
            census = len(curr_shift_residents_acuity)
            n_staff_to_assign = census
            for j in range(n_staff_to_assign):
                assigned_staff = nurses[(i + j) % staff_count]
                shift_assignments.setdefault(
                    shift.shift_key,
                    [],
                ).append(assigned_staff.employee_id)

        return Schedule(
            org_id="baseline_org",
            facility_id=shifts[0].facility_id,
            schedule_id="1",
            shift_assignments=shift_assignments,
        )
