import whenever

from snf_schedule_optimizer.datetime_utils import is_weekend
from snf_schedule_optimizer.models import (
    Differential,
    DifferentialDateInterval,
    DifferentialRuleType,
    Shift,
)
from snf_schedule_optimizer.models.persistence_dtos import DifferentialRuleData
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
        if is_weekend(shift.shift_start_dt.date().day_of_week()):
            return [
                DifferentialDateInterval(shift.shift_start_dt, shift.shift_end_dt, self)
            ]
        return []


class PatternDifferentialRule(IDifferentialRule):
    """
    Unified implementation of a differential rule.
    Decides applicable intervals based on metadata (Nights, Weekends, etc.)
    """

    def __init__(self, data: DifferentialRuleData):
        self._data = data

    def get_applicable_intervals_for_shift(
        self, shift: Shift
    ) -> list[DifferentialDateInterval]:
        """
        Calculates which parts of the shift (if any) are eligible for this pay.
        """
        # 1. Check Weekend Rule
        if self._data.rule_type == DifferentialRuleType.WEEKEND:
            # If start or end is on a weekend, apply to whole shift for now (simple logic)
            if shift.day_of_week in (whenever.SATURDAY, whenever.SUNDAY):
                return [
                    DifferentialDateInterval(
                        shift.shift_start_dt,
                        shift.shift_end_dt,
                        rule=self,
                    )
                ]
            return []

        # 2. Check Night/Time-based Rule
        if self._data.rule_type in (
            DifferentialRuleType.NIGHT_SHIFT,
            DifferentialRuleType.FIXED_TIME,
        ):
            # This would use the slicer/intersection logic
            # Returning empty for now as a placeholder
            return []

        # 3. Check Global Rule
        if self._data.rule_type == DifferentialRuleType.ALL_HOURS:
            return [
                DifferentialDateInterval(
                    shift.shift_start_dt,
                    shift.shift_end_dt,
                    rule=self,
                )
            ]

        return []

    @property
    def differential(self) -> Differential:
        return Differential(
            name=self._data.description,
            d_type=self._data.differential_type,
            multiplier=self._data.multiplier,
            flat=self._data.flat,
        )

    @property
    def priority(self) -> int:
        return self._data.priority

    @property
    def applicable_job_titles(self) -> list[str] | None:
        return self._data.applicable_job_titles
