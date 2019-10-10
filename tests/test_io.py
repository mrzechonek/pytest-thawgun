import asyncio
import functools

import pytest

pytestmark = pytest.mark.asyncio


async def test_queue(event_loop, thawgun):
    async def server(reader, writer, delay):
        while True:
            data = await reader.get()
            await asyncio.sleep(delay)
            await writer.put(data)

            if data == '!':
                break

    async def client(reader, writer, text, delay):
        received = ''

        for i in text:
            await reader.put(i)
            received += await asyncio.wait_for(writer.get(), delay + 1e-6)

        return received

    reader = asyncio.Queue()
    writer = asyncio.Queue()

    text = 'Time travel!'

    server_task = event_loop.create_task(server(reader, writer, 1.0))
    client_task = event_loop.create_task(client(reader, writer, text, 1.0))

    await thawgun.advance(len(text))

    assert await asyncio.wait_for(client_task, 0) == text
    await asyncio.wait_for(server_task, 0)


async def test_io(event_loop, thawgun):

    async def server(reader, writer, delay):
        while True:
            data = await reader.read(1)
            if not data:
                break

            await asyncio.sleep(delay)
            writer.write(data)

            if data == b'!':
                break

        writer.close()


    async def client(reader, writer, text, delay):
        received = b''

        for i in text:
            writer.write(bytes([i]))

            data = await asyncio.wait_for(reader.read(1), delay + 1e-6)
            if not data:
                break

            received += data

        writer.close()

        return received

    text = b'Time travel!'

    server_task = await asyncio.start_server(functools.partial(server, delay=1.0),
                                             'localhost', 1234)

    reader, writer = await asyncio.open_connection('localhost', 1234)

    client_task = event_loop.create_task(client(reader, writer, text, 1.0))

    await thawgun.advance(len(text))

    assert await asyncio.wait_for(client_task, 0) == text

    server_task.close()
    await server_task.wait_closed()


