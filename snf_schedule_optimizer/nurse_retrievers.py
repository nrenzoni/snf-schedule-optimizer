import abc
from typing import List

from snf_schedule_optimizer.data_models import NurseProfile, Shift


class INurseRetriever(abc.ABC):
    @abc.abstractmethod
    def get_nurses(
            self,
            shift: Shift,
    ) -> List[NurseProfile]:
        pass


class NurseRetrieverImpl(INurseRetriever):
    def __init__(
            self,
            nurses: List[NurseProfile],
    ):
        self.nurses = nurses

    def get_nurses(
            self,
            shift: Shift,
    ) -> List[NurseProfile]:
        # In a real implementation, filter nurses based on availability, skills, etc.
        return self.nurses
