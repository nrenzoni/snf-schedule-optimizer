from snf_schedule_optimizer.datetime_utils import is_weekend
from snf_schedule_optimizer.models import Differential, DifferentialDateInterval, Shift
from snf_schedule_optimizer.services.payroll.interfaces import IDifferentialRule


class DailyPatternDifferentialRule(IDifferentialRule):
    def __init__(
        self,
        differential: Differential,
    ):
        # Store the defined differential rate
        self._differential = differential
        # Add pattern-specific config here (e.g., self.start_time = 19:00, self.end_time = 07:00)

    @property
    def differential(self) -> Differential:
        return self._differential

    @property
    def priority(self) -> int:
        raise NotImplementedError()

    @property
    def applicable_job_titles(self) -> list[str] | None:
        raise NotImplementedError()

    def get_applicable_intervals_for_shift(
        self,
        shift: Shift,
    ) -> list[DifferentialDateInterval]:
        if is_weekend(shift.shift_start_dt.day_of_week):
            return [
                DifferentialDateInterval(shift.shift_start_dt, shift.shift_end_dt, self)
            ]
        return []
