from datetime import datetime

import pytest

from agentsociety2.contrib.env.event_space.environment import EventSpace


@pytest.mark.asyncio
async def test_event_space_absorbs_same_tick_same_type_restart() -> None:
    env = EventSpace()
    await env.init(datetime(2026, 1, 2, 0, 0))

    first = await env.start_event(1, "sleep", "night sleep", 28800)
    stopped = await env.stop_event(1, "cancelled")
    second = await env.start_event(1, "sleep", "sleeping at home", 25200)
    current = await env.get_current_event(1)

    assert stopped.success is True
    assert second.start_time == first.start_time
    assert second.event_name == "night sleep"
    assert current is not None
    assert current.event_type == "sleep"
    assert current.event_name == "night sleep"
    assert current.elapsed_seconds == 0


@pytest.mark.asyncio
async def test_event_space_treats_sleep_duration_minute_like_values_as_minutes() -> None:
    env = EventSpace()
    await env.init(datetime(2026, 1, 2, 0, 0))

    event = await env.start_event(1, "sleep", "night sleep", 420)

    assert (event.expected_end_time - event.start_time).total_seconds() == 25200


@pytest.mark.asyncio
async def test_event_space_treats_small_sleep_duration_values_as_minutes_or_hours() -> None:
    env = EventSpace()
    await env.init(datetime(2026, 1, 2, 0, 0))

    thirty_minutes = await env.start_event(1, "sleep", "short nap", 30)
    seven_and_half_hours = await env.start_event(2, "sleep", "night sleep", 7.5)

    assert (
        thirty_minutes.expected_end_time - thirty_minutes.start_time
    ).total_seconds() == 1800
    assert (
        seven_and_half_hours.expected_end_time - seven_and_half_hours.start_time
    ).total_seconds() == 27000


@pytest.mark.asyncio
async def test_event_space_absorbs_same_type_active_start_without_shortening() -> None:
    env = EventSpace()
    await env.init(datetime(2026, 1, 2, 0, 0))

    first = await env.start_event(1, "sleep", "night sleep", 25200)
    await env.step(900, datetime(2026, 1, 2, 0, 15))
    second = await env.start_event(1, "sleep", "mistaken 30 second sleep", 30)
    current = await env.get_current_event(1)

    assert second.start_time == first.start_time
    assert second.event_name == "night sleep"
    assert second.expected_end_time == first.expected_end_time
    assert current is not None
    assert current.elapsed_seconds == 900
    assert current.expected_end_time == first.expected_end_time


@pytest.mark.asyncio
async def test_event_space_absorbs_cross_step_same_type_restart() -> None:
    env = EventSpace()
    await env.init(datetime(2026, 1, 2, 0, 0))

    first = await env.start_event(1, "sleep", "night sleep", 25200)
    await env.step(900, datetime(2026, 1, 2, 0, 15))
    await env.stop_event(1, "cancelled")
    second = await env.start_event(1, "sleep", "sleep until 07:00", 24300)
    current = await env.get_current_event(1)

    assert second.start_time == first.start_time
    assert second.event_name == "night sleep"
    assert current is not None
    assert current.elapsed_seconds == 900
    assert (current.expected_end_time - first.start_time).total_seconds() == 25200


@pytest.mark.asyncio
async def test_event_space_ignores_passive_wait_after_real_event_stop() -> None:
    env = EventSpace()
    await env.init(datetime(2026, 1, 2, 0, 0))

    first = await env.start_event(10, "sleep", "night sleep", 25200)
    await env.stop_event(10, "cancelled")
    second = await env.start_event(10, "other", "Waiting for 30 minutes", 1800)
    current = await env.get_current_event(10)

    assert second.event_type == "sleep"
    assert second.event_name == "night sleep"
    assert second.expected_end_time == first.expected_end_time
    assert current is not None
    assert current.event_type == "sleep"
