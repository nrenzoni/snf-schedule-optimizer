import abc
from typing import NamedTuple

from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    PreferenceWeights,
    Schedule,
    Shift,
    ShiftSpecificRequirements,
)


class IShiftRequirementsRepo(abc.ABC):
    @abc.abstractmethod
    async def get_shift_requirements(
        self, shift: Shift
    ) -> ShiftSpecificRequirements | None:
        pass


class IPreferencePenaltyProcessor(abc.ABC):
    """Defines the service for calculating non-financial penalties for soft constraints."""

    @abc.abstractmethod
    async def calculate_penalty_cost(
        self,
        employee: Employee,
        nurse: NurseProfile,
        shift: Shift,
        preference_weights: PreferenceWeights,
    ) -> float:
        """
        Calculates the non-financial penalty cost if the assignment violates a soft preference.
        This cost is added to the LP objective function.
        """
        pass


class ScheduleLookupKey(NamedTuple):
    org_id: str
    schedule_id: str


class IScheduleRepo(abc.ABC):
    """
    Interface for retrieving Schedule objects (assignments) from persistence.
    """

    @abc.abstractmethod
    async def get_schedule(self, schedule_lookup: ScheduleLookupKey) -> Schedule | None:
        """
        Retrieves the schedule assignments for a specific schedule ID.
        Returns None if not found.
        """
        pass
