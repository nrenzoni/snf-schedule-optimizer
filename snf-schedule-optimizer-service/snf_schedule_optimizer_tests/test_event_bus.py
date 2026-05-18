import pytest

from snf_schedule_optimizer.domain.events import SchedulePublished
from snf_schedule_optimizer.infrastructure.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_publish_and_subscribe() -> None:
    bus = EventBus()
    received: list[SchedulePublished] = []

    async def handler(event: SchedulePublished) -> None:
        received.append(event)

    bus.subscribe(SchedulePublished, handler)

    event = SchedulePublished(org_id=1, facility_id=2, schedule_id=3, version=4)
    await bus.publish(event)

    assert len(received) == 1
    assert received[0].org_id == 1
    assert received[0].facility_id == 2


@pytest.mark.asyncio
async def test_event_bus_multiple_handlers() -> None:
    bus = EventBus()
    count = 0

    async def handler1(event: SchedulePublished) -> None:
        nonlocal count
        count += 1

    async def handler2(event: SchedulePublished) -> None:
        nonlocal count
        count += 1

    bus.subscribe(SchedulePublished, handler1)
    bus.subscribe(SchedulePublished, handler2)

    event = SchedulePublished(org_id=1, facility_id=2, schedule_id=3, version=4)
    await bus.publish(event)

    assert count == 2


@pytest.mark.asyncio
async def test_event_bus_handler_error_does_not_break_others() -> None:
    bus = EventBus()
    good_count = 0

    async def failing_handler(event: SchedulePublished) -> None:
        raise RuntimeError("handler failed")

    async def good_handler(event: SchedulePublished) -> None:
        nonlocal good_count
        good_count += 1

    bus.subscribe(SchedulePublished, failing_handler)
    bus.subscribe(SchedulePublished, good_handler)

    event = SchedulePublished(org_id=1, facility_id=2, schedule_id=3, version=4)
    await bus.publish(event)  # Should not raise

    assert good_count == 1
