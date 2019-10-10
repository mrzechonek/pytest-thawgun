import asyncio
import time
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.asyncio
_dt = datetime.utcfromtimestamp


def assert_clocks_are_ticking(loop):
    wall_then, loop_then = time.time(), loop.time()
    time.sleep(0.001)
    wall_now, loop_now = time.time(), loop.time()
    assert _dt(loop_now) > _dt(loop_then), "Loop clock not ticking!"
    assert _dt(wall_now) > _dt(wall_then), "Wall clock not ticking!"


def assert_clocks_are_stopped(loop):
    wall_then, loop_then = time.time(), loop.time()
    time.sleep(0.001)
    wall_now, loop_now = time.time(), loop.time()
    assert _dt(loop_then) == _dt(loop_now), "Loop clock still ticking!"
    assert _dt(wall_then) == _dt(wall_now), "Wall clock still ticking!"


def assert_clocks_progressed_by(loop, wall_ref, loop_ref, seconds):
    assert _dt(time.time()) == _dt(wall_ref) + timedelta(seconds=seconds)
    assert _dt(loop.time()) == _dt(loop_ref) + timedelta(seconds=seconds)


async def counter(count, before=None, after=None):
    for i in range(count):
        if before:
            before(i)

        await asyncio.sleep(1)

        if after:
            after(i)

        await asyncio.sleep(1)

    return count


async def test_sleep(event_loop, thawgun):
    befores = []
    def before(count):
        befores.append((count, datetime.now()))

    afters = []
    def after(count):
        afters.append((count, datetime.now()))

    task = event_loop.create_task(counter(10, before, after))

    start, end = await thawgun.advance(20)

    assert befores == [(i, start + timedelta(seconds=i * 2)) for i in range(10)]
    assert afters == [(i, start + timedelta(seconds=i * 2 + 1)) for i in range(10)]

    await asyncio.wait_for(task, 0)


async def test_wait_for(event_loop, thawgun):
    task = event_loop.create_task(asyncio.wait_for(counter(3), timeout=7))
    await thawgun.advance(7)
    assert await asyncio.wait_for(task, 0) == 3


async def test_nesting(event_loop, thawgun):
    async def nested(level):
        await asyncio.sleep(1)

        if level > 0:
            level += await event_loop.create_task(nested(level - 1))

        return level

    task = event_loop.create_task(nested(10))
    await thawgun.advance(11)
    assert await asyncio.wait_for(task, 0) == sum(range(11))


async def test_gather(thawgun):
    task = asyncio.gather(counter(5), counter(3), counter(10))
    await thawgun.advance(20)
    assert await asyncio.wait_for(task, 0) == [5, 3, 10]


async def test_clocks_are_ticking_with_multiple_advance_calls(event_loop, thawgun):
    await thawgun.advance(1)
    assert_clocks_are_ticking(event_loop)
    await thawgun.advance(1)
    assert_clocks_are_ticking(event_loop)


@pytest.mark.parametrize("no_of_advances", [1, 2, 10])
async def test_time_stops(event_loop, thawgun, no_of_advances):
    with thawgun as tg:
        wall_ref, loop_ref = time.time(), event_loop.time()

        for _ in range(no_of_advances):
            await tg.advance(1)

        assert_clocks_progressed_by(event_loop, wall_ref, loop_ref, no_of_advances)


@pytest.mark.parametrize("start", [0, time.time() + 10.0])
async def test_adjustable_time_of_start(thawgun, start):
    with thawgun as tg:
        tg.set_wall_clock(_dt(start))
        await tg.advance(5)

        now = time.time()
        expected_now = (start + 5.0)

        assert _dt(now) == _dt(expected_now)


async def test_clock_stops_inside_context_manager(thawgun):
    assert_clocks_are_ticking(thawgun.loop)

    with thawgun:
        assert_clocks_are_stopped(thawgun.loop)

    assert_clocks_are_ticking(thawgun.loop)


async def test_clock_can_move_inside_context_manager(thawgun):
    target = datetime(year=2000, month=1, day=1)
    with thawgun as tg:
        tg.set_wall_clock(to=target)
        assert datetime.now() == target


async def test_multiple_context_use(thawgun):
    with thawgun:
        assert_clocks_are_stopped(thawgun.loop)

    assert_clocks_are_ticking(thawgun.loop)

    with thawgun:
        assert_clocks_are_stopped(thawgun.loop)
