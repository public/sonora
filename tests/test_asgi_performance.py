import asyncio

import pytest

import sonora.aio
from tests import benchmark_pb2, benchmark_pb2_grpc


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_asgi_unarycall(asgi_benchmark, benchmark, event_loop, size):
    request = benchmark_pb2.SimpleRequest(response_size=size)

    async def run():
        for _ in range(10):
            message = await asgi_benchmark.UnaryCall(request)
        assert len(message.payload.body) == size

    def perf():
        event_loop.run_until_complete(run())

    benchmark(perf)


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_asgi_streamingfromserver(asgi_benchmark, event_loop, benchmark, size):

    chunk_count = 10

    request = benchmark_pb2.SimpleRequest(response_size=size)
    request.payload.body = b"\0" * size

    async def run():
        recv_bytes = 0
        n = 0

        with asgi_benchmark.StreamingFromServer(request) as stream:
            async for message in stream:
                recv_bytes += len(message.payload.body)
                n += 1
                if n >= chunk_count:
                    break

        assert recv_bytes == size * chunk_count

    def perf():
        event_loop.run_until_complete(run())

    benchmark(perf)
