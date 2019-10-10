import asyncio
import logging
from asyncio import AbstractEventLoop
from datetime import datetime

import pytest
from freezegun import freeze_time
from typing import Tuple

__all__ = ['thawgun']


class ThawGun:
    def __init__(self, loop: AbstractEventLoop):
        self.loop = loop
        self.loop._real_time = self.loop.time
        self._logger = logging.getLogger(self.__class__.__name__)
        self._do_tick = True
        self._frozen_wall_clock_control = None
        self._freeze_time = None

    async def _drain(self, drain_time: float) -> None:
        """
        Allow the loop to execute all the code at given point in time.

        Caveat: assumes that all the events scheduled for earlier
        than drain_time have already been executed.

        :param drain_time: all code scheduled at this timestamp will be executed
        """
        while True:
            await asyncio.sleep(0)

            if not self.loop._scheduled:
                break

            if self.loop._scheduled[0]._when > drain_time:
                break

        while self.loop._ready:
            await asyncio.sleep(0)

    def __enter__(self):
        self._do_tick = False
        self.set_wall_clock(to=datetime.now())
        self._adjust_loop_clock(to=self.loop.time())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._do_tick = True
        self._adjust_loop_clock(to=self.loop.time())
        self.set_wall_clock(to=datetime.now())

    def _adjust_loop_clock(self, to: float) -> None:
        """
        Moves loop clock to a specific timestamp, making sure that external observers do not see the introduced
        non-linearity.
        :param to: target timestamp
        """
        if self._do_tick:
            loop_real_time_drift = self.loop._real_time() - to
            self.loop.time = lambda: self.loop._real_time() - loop_real_time_drift
        else:
            self.loop.time = lambda: to

    def set_wall_clock(self, to: datetime) -> None:
        """
        Moves wall clock to a specific datetime, preserving current mode of operation.

        :param to: target datetime
        """
        if self._freeze_time is not None:
            self._freeze_time.stop()
        self._freeze_time = freeze_time(to, tick=self._do_tick)
        self._frozen_wall_clock_control = self._freeze_time.start()

    async def advance(self, offset: float) -> Tuple[datetime, datetime]:
        """
        Advance both loop and wall clocks by offset, preserving mode of operation.

        :param offset:
        :return: datetimes at the beginning and end of advance() call
        """
        assert offset >= 0, "Can't go backwards"

        prev_ticking_state = self._do_tick
        self._do_tick = False

        advance_start_dt = advance_end_dt = datetime.now()
        self.set_wall_clock(advance_start_dt)

        self._adjust_loop_clock(self.loop.time())

        loop_target_time = self.loop.time() + offset

        try:
            await self._drain(self.loop.time())

            while self.loop._scheduled and self.loop._scheduled[0]._when <= loop_target_time:
                handle = self.loop._scheduled[0]
                prev_drain_time = self.loop.time()
                this_drain_time = handle._when

                self._frozen_wall_clock_control.tick(this_drain_time - prev_drain_time)

                self._adjust_loop_clock(this_drain_time)
                advance_end_dt = datetime.now()

                if not handle._cancelled:
                    handle._run()
                    handle._callback, handle._args = lambda: None, ()

                await self._drain(self.loop.time())

            self._frozen_wall_clock_control.tick(loop_target_time - self.loop.time())

            self._adjust_loop_clock(loop_target_time)
            await self._drain(self.loop.time())

            advance_end_dt = datetime.now()

        finally:
            self._do_tick = prev_ticking_state
            self._adjust_loop_clock(loop_target_time)
            self.set_wall_clock(advance_end_dt)

        return advance_start_dt, advance_end_dt

    def test_teardown(self) -> None:
        """
        Fix time displayed after the test, e.g. in pytest summary
        """
        self._freeze_time.stop()
        self.loop.time = self.loop._real_time
        del self.loop._real_time


@pytest.fixture
def thawgun(event_loop):
    tg = ThawGun(loop=event_loop)
    yield tg
    tg.test_teardown()
