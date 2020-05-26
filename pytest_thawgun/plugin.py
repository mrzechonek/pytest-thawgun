import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timedelta

import pytest
from async_generator import async_generator, yield_
from freezegun import freeze_time

__all__ = ["thawgun"]


class ThawGun:
    def __init__(self, loop):
        self.loop = loop
        self.offset = 0
        self.real_time = self.loop.time
        self.real_select = self.loop._selector.select
        self.loop.time = self.time
        self.logger = logging.getLogger(self.__class__.__name__)
        self.freeze_time = freeze_time(tick=True)
        self.freeze_time.start()
        self.wall_offset = None

    def time(self):
        return self.real_time() + self.offset

    def _datetime(self, current_time):
        return datetime.fromtimestamp(current_time) + self.wall_offset

    async def _drain(self):
        while True:
            ready = deque(self.loop._ready)
            scheduled = list(self.loop._scheduled)

            await asyncio.sleep(0)

            if self.loop._ready:
                continue

            if self.loop._scheduled != scheduled:
                continue

            if self.loop._ready == ready:
                break

    async def advance(self, offset_or_new_time):
        base_time = current_time = self.time()
        self.wall_offset = timedelta(seconds=time.time() - self.time())

        if isinstance(offset_or_new_time, datetime):
            offset = (offset_or_new_time - self.wall_offset).timestamp() - base_time
        elif isinstance(offset_or_new_time, timedelta):
            offset = offset_or_new_time.total_seconds()
        else:
            offset = offset_or_new_time

        assert offset >= 0, "Can't go backwards"

        new_time = base_time + offset

        try:
            with freeze_time(self._datetime(current_time)) as ft:
                self.loop.time = lambda: current_time
                self.loop._selector.select = lambda timeout: self.real_select(
                    timeout or self.loop._clock_resolution
                )

                self.logger.debug("Freeze: %s", self._datetime(current_time))

                # keep iterating the loop until we reach target time, or there
                # is nothing more to do
                while current_time < new_time and (
                    self.loop._ready or self.loop._scheduled
                ):
                    await self._drain()

                    while self.loop._scheduled:
                        handle = self.loop._scheduled[0]

                        if handle._when > new_time:
                            current_time = new_time
                            break

                        current_time = handle._when
                        ft.move_to(self._datetime(current_time))

                        self.logger.debug("Advance: %s", self._datetime(current_time))

                        if not handle._cancelled:
                            handle._run()
                            handle._callback, handle._args = lambda: None, ()

                        await self._drain()

        finally:
            self.offset += offset
            self.loop.time = self.time
            self.loop._selector.select = self.real_select

        start, end = (self._datetime(base_time), self._datetime(new_time))

        self.freeze_time = freeze_time(self._datetime(new_time), tick=True)
        self.logger.debug("Thaw: %s", self._datetime(new_time))
        self.freeze_time.start()

        return start, end


@pytest.fixture
@async_generator
async def thawgun(event_loop):
    await yield_(ThawGun(event_loop))
