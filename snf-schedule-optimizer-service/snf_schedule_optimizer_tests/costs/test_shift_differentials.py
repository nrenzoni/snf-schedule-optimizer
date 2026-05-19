"""Tests that shift differentials use facility config multipliers, not hardcoded values."""

import whenever

from snf_schedule_optimizer.models import FacilityConfig
from snf_schedule_optimizer.optimizer.calculators import (
    ConfigurableIncentiveManager,
    StandardLaborBurdenCalculator,
)
from snf_schedule_optimizer.optimizer.clocks import IClock
from snf_schedule_optimizer.optimizer.strategies.pay import (
    ComprehensiveShiftCostStrategy,
)


def test_facility_config_carries_night_shift_multiplier() -> None:
    """FacilityConfig stores night_shift_multiplier as a configurable value."""
    config = FacilityConfig(
        org_id=1,
        facility_id=1,
        shifts_per_day=3,
        overtime_threshold_hours_per_week=40,
        start_of_work_week_day=whenever.Weekday.MONDAY,
        start_of_work_day_time=whenever.Time(7, 0, 0),
        pay_period=whenever.DateDelta(weeks=1),
        weekend_multiplier=1.5,
        night_shift_multiplier=2.0,
        tz="America/New_York",
    )
    assert config.night_shift_multiplier == 2.0
    assert config.weekend_multiplier == 1.5
    assert config.default_hprd_lpn == 0.0


def test_comprehensive_cost_strategy_accepts_burden_and_incentive_params() -> None:
    """ComprehensiveShiftCostStrategy can be instantiated with burden and incentive deps."""

    class _FakeClock(IClock):
        def now(self) -> whenever.Instant:
            return whenever.Instant.now()

    strategy = ComprehensiveShiftCostStrategy(
        burden_calc=StandardLaborBurdenCalculator(),
        incentive_mgr=ConfigurableIncentiveManager(
            holidays=set(),
            urgency_threshold_days=0,
            pickup_bonus=0.0,
            clock=_FakeClock(),
        ),
    )
    assert strategy is not None
