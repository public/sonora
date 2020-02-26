import pytest

import sonora.client
from tests import benchmark_pb2, benchmark_pb2_grpc


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_wsgi_unarycall(wsgi_benchmark, benchmark, size):
    request = benchmark_pb2.SimpleRequest(response_size=size)

    def perf():
        for _ in range(10):
            message = wsgi_benchmark.UnaryCall(request)
        assert len(message.payload.body) == size

    benchmark(perf)


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_wsgi_streamingfromserver(wsgi_benchmark, benchmark, size):
    chunk_count = 10

    request = benchmark_pb2.SimpleRequest(response_size=size)
    request.payload.body = b"\0" * size

    def perf():
        recv_bytes = 0
        n = 0

        for message in wsgi_benchmark.StreamingFromServer(request):
            recv_bytes += len(message.payload.body)
            n += 1
            if n >= chunk_count:
                break

        assert recv_bytes == size * chunk_count

    benchmark(perf)
