import abc

from snf_schedule_optimizer.models import (
    Employee,
    NurseProfile,
    PreferenceWeights,
    Shift,
    ShiftSpecificRequirements,
)


class IShiftRequirementsRetriever(abc.ABC):
    @abc.abstractmethod
    def get_shift_requirements(self, shift: Shift) -> ShiftSpecificRequirements:
        pass


class IPreferencePenaltyProcessor(abc.ABC):
    """Defines the service for calculating non-financial penalties for soft constraints."""

    @abc.abstractmethod
    def calculate_penalty_cost(
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
