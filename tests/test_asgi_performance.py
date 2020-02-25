import pytest

import sonora.aio
from tests import benchmark_pb2, benchmark_pb2_grpc


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_asgi_unarycall(asgi_benchmark, benchmark, event_loop, size):
    async def run():
        request = benchmark_pb2.SimpleRequest(response_size=size)

        for _ in range(1000):
            message = await asgi_benchmark.UnaryCall(request)
            assert len(message.payload.body) == size

    def perf():
        event_loop.run_until_complete(run())

    benchmark(perf)


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_asgi_streamingfromserver(asgi_benchmark, event_loop, benchmark, size):

    request_count = 10
    chunk_count = 100

    async def run():
        request = benchmark_pb2.SimpleRequest(response_size=size)
        request.payload.body = b"\0" * size

        recv_bytes = 0

        for _ in range(request_count):
            n = 0
            async for message in asgi_benchmark.StreamingFromServer(request):
                recv_bytes += len(message.payload.body)
                n += 1
                if n >= chunk_count:
                    break

            assert n == chunk_count

        assert recv_bytes == size * request_count * chunk_count

    def perf():
        event_loop.run_until_complete(run())

    benchmark(perf)
