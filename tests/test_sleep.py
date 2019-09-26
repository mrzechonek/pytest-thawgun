import asyncio
import contextlib
from datetime import datetime
from concurrent.futures import CancelledError

from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.asyncio


async def counter(count, before = None, after = None):
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


async def test_gather(event_loop, thawgun):
    task = asyncio.gather(counter(5), counter(3), counter(10))
    await thawgun.advance(20)
    assert await asyncio.wait_for(task, 0) == [5, 3, 10]
