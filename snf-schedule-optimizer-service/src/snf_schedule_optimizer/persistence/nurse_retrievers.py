import abc

from snf_schedule_optimizer.models import NurseProfile, Shift


class INurseRetriever(abc.ABC):
    @abc.abstractmethod
    def get_nurses(
        self,
        shift: Shift,
    ) -> list[NurseProfile]:
        pass

    @abc.abstractmethod
    def get_nurse(
        self,
        employee_id: str,
    ) -> NurseProfile | None:
        pass


class NurseRetrieverStaticListImpl(INurseRetriever):
    def __init__(
        self,
        nurses: list[NurseProfile],
    ):
        self.nurses = nurses
        self.nurse_dict = {n.employee_id: n for n in nurses}

    def get_nurses(
        self,
        shift: Shift,
    ) -> list[NurseProfile]:
        # In a real implementation, filter nurses based on availability, skills, etc.
        return self.nurses

    def get_nurse(self, employee_id: str) -> NurseProfile | None:
        return self.nurse_dict[employee_id]
