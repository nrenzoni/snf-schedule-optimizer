from collections import defaultdict

from snf_schedule_optimizer.models import (
    Schedule,
    ShiftAssignmentsType,
    ShiftKey,
)
from snf_schedule_optimizer.optimizer.context import LpNurseShiftVariableHolder


class ScheduleExtractor:
    """
    Translates raw LP solver variables into a domain Schedule object.
    Separates solver implementation details from domain models.
    """

    def extract(
        self,
        lp_holder: LpNurseShiftVariableHolder,
        org_id: str,
        facility_id: str | None = None,
    ) -> Schedule:
        shift_assignments: ShiftAssignmentsType = defaultdict(list)

        # Iterate over the structured Tuple keys
        for key, variable in lp_holder.get_all_assignments().items():
            # Check the resolved value
            # 0.5 threshold handles floating point imprecision (e.g. 0.9999 vs 1.0)
            if variable.varValue and variable.varValue > 0.5:
                shift_assignments[ShiftKey(key.facility_id, key.shift.shift_id)].append(
                    key.employee_id
                )

        return Schedule(
            org_id,
            facility_id,
            None,
            shift_assignments,
        )
