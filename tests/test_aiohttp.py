import asyncio
import contextlib
import functools
import logging
import multiprocessing
import time
from concurrent import futures
from itertools import count

import aiohttp.web
import pytest
import requests
from aiohttp.client_exceptions import ClientConnectionError

pytestmark = pytest.mark.asyncio


def application():
    counter = count()

    async def get_counter(request):
        await asyncio.sleep(1.0)
        return aiohttp.web.Response(body=str(next(counter)), content_type="text/plain")

    app = aiohttp.web.Application()
    app.add_routes([aiohttp.web.get("/counter", get_counter)])

    return app


@pytest.fixture
async def async_server():
    runner = aiohttp.web.AppRunner(application())
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host="localhost", port=1234)
    await site.start()

    yield

    await runner.cleanup()


@pytest.fixture
def subprocess_server():
    server = multiprocessing.Process(
        target=aiohttp.web.run_app,
        args=[application()],
        kwargs=dict(host="localhost", port=1234),
    )

    server.start()

    # make sure the server is up
    for i in range(10):
        with contextlib.suppress(requests.ConnectionError):
            requests.get("http://localhost:1234")
            break
        time.sleep(0.1)

    yield

    server.terminate()
    server.join()


async def get_counters(iterations, timeout=None):
    responses = []

    kwargs = dict(timeout=aiohttp.ClientTimeout(timeout)) if timeout else {}
    async with aiohttp.ClientSession(**kwargs) as session:
        for i in range(iterations):
            try:
                async with session.get("http://localhost:1234/counter") as response:
                    body = await response.text()
                    responses.append(int(body))
            except futures.TimeoutError:
                responses.append(None)

    return responses


async def test_aiohttp_async(async_server, event_loop, thawgun):
    task = event_loop.create_task(get_counters(10))

    await thawgun.advance(5)
    await thawgun.advance(5)

    assert (await task) == list(range(10))


async def test_aiohttp_subprocess(subprocess_server, event_loop, thawgun):

    task = event_loop.create_task(get_counters(10, timeout=1.0))

    await thawgun.advance(11)

    # we can't control subprocess time, so everything is going to expire immediately
    assert (await task) == [None] * 10
