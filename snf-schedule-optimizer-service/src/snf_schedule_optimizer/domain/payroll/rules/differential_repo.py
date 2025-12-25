from snf_schedule_optimizer.datetime_utils import is_weekend
from snf_schedule_optimizer.domain.payroll.interfaces import (
    INurseDifferentialRepo,
)
from snf_schedule_optimizer.models import (
    Differential,
    DifferentialType,
    FacilityConfig,
    NurseProfile,
    Shift,
)


class NurseDifferentialRepoImpl(INurseDifferentialRepo):
    def __init__(self, facility_config: FacilityConfig):
        self.facility_config = facility_config

    def get_differentials(
        self,
        nurse: NurseProfile,
        shift: Shift,
    ) -> list[Differential]:
        if is_weekend(shift.day_of_week):
            return [
                Differential(
                    name="Weekend Shift Differential",
                    d_type=DifferentialType.MULTIPLIER,
                    multiplier=self.facility_config.weekend_multiplier,
                )
            ]
        if not shift.day_shift:
            return [
                Differential(
                    name="Night Shift Differential",
                    d_type=DifferentialType.MULTIPLIER,
                    multiplier=self.facility_config.night_shift_multiplier,
                )
            ]
        return []
