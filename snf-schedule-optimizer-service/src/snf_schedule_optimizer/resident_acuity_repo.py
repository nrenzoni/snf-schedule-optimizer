import abc

from snf_schedule_optimizer.models import ResidentAcuity, Shift


class IResidentAcuityPerShiftRepo(abc.ABC):
    @abc.abstractmethod
    async def get_resident_acuity_list(
        self,
        shift: Shift,
    ) -> list[ResidentAcuity]:
        pass


class FakeResidentAcuityPerShiftRepo(IResidentAcuityPerShiftRepo):
    """Same resident acuity for all shifts - for testing purposes."""

    def __init__(
        self,
        predefined_acuity_data: list[ResidentAcuity],
    ):
        self.stressed_residents: list[ResidentAcuity] = predefined_acuity_data

    async def get_resident_acuity_list(
        self,
        shift: Shift,
    ) -> list[ResidentAcuity]:
        return [
            r
            for r in self.stressed_residents
            if r.census_day.date() == shift.shift_start_dt.date()
        ]
