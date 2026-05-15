"""Tests for overtime pay strategy instantiation and employee-id resolution."""

from snf_schedule_optimizer.optimizer.strategies.pay import (
    DailyOvertimePayStrategy,
    WeeklyVolumePayStrategy,
)


async def test_daily_overtime_strategy_can_instantiate() -> None:
    processor = object()
    strategy = DailyOvertimePayStrategy(processor)  # type: ignore[arg-type]
    assert strategy.shift_pay_processor is processor


async def test_weekly_volume_strategy_can_instantiate() -> None:
    processor = object()
    strategy = WeeklyVolumePayStrategy(processor, threshold=40.0)  # type: ignore[arg-type]
    assert strategy.threshold == 40.0
    assert strategy.shift_pay_processor is processor
