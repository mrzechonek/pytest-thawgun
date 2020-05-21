import asyncio
import logging
import time
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
        await asyncio.sleep(0)

        while self.loop._ready:
            await asyncio.sleep(0)

    async def advance(self, offset):
        assert offset >= 0, "Can't go backwards"

        try:
            base_time = current_time = self.time()
            new_time = base_time + offset
            self.wall_offset = timedelta(seconds=time.time() - self.time())

            with freeze_time(self._datetime(current_time)) as ft:
                self.loop.time = lambda: current_time

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

        start, end = (self._datetime(base_time), self._datetime(new_time))

        self.freeze_time = freeze_time(self._datetime(new_time), tick=True)
        self.logger.debug("Thaw: %s", self._datetime(new_time))
        self.freeze_time.start()

        return start, end


@pytest.fixture
@async_generator
async def thawgun(event_loop):
    await yield_(ThawGun(event_loop))
