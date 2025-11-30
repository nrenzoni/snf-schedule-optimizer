import abc
from typing import List

from snf_schedule_optimizer.models import ResidentAcuity, Shift


class IResidentAcuityPerShiftRetriever(abc.ABC):
    @abc.abstractmethod
    def get_resident_acuity_list(
        self,
        shift: Shift,
    ) -> List[ResidentAcuity]:
        pass


class ResidentAcuityPerShiftRetrieverImpl(IResidentAcuityPerShiftRetriever):
    """Same resident acuity for all shifts - for testing purposes."""

    def __init__(
        self,
        predefined_acuity_data: List[ResidentAcuity],
    ):
        self.stressed_residents: List[ResidentAcuity] = predefined_acuity_data

    def get_resident_acuity_list(
        self,
        shift: Shift,
    ) -> List[ResidentAcuity]:
        return self.stressed_residents
