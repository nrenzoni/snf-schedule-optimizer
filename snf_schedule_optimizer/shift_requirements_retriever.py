import abc

from snf_schedule_optimizer.models import Shift, ShiftSpecificRequirements


class IShiftRequirementsRetriever(abc.ABC):
    @abc.abstractmethod
    def get_shift_requirements(self, shift: Shift) -> ShiftSpecificRequirements:
        pass


class ShiftRequirementsRetrieverImpl(IShiftRequirementsRetriever):
    """same requirements for all shifts implementation"""

    def __init__(self, default_requirements: ShiftSpecificRequirements):
        self.default_requirements = default_requirements

    def get_shift_requirements(self, shift: Shift) -> ShiftSpecificRequirements:
        return self.default_requirements
