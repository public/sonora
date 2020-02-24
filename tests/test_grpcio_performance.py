import pytest
import time
import grpc

from tests import benchmark_pb2, benchmark_pb2_grpc


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_grpcio_unarycall(grpcio_benchmark, benchmark, size):
    def perf():
        request = benchmark_pb2.SimpleRequest(response_size=size)

        for _ in range(1000):
            message = grpcio_benchmark.UnaryCall(request)
            assert len(message.payload.body) == size

    benchmark(perf)


@pytest.mark.parametrize("size", [1, 100, 10000, 1000000])
def test_grpcio_streamingfromserver(grpcio_benchmark, benchmark, size):

    request_count = 10
    chunk_count = 100

    def perf():
        request = benchmark_pb2.SimpleRequest(response_size=size)
        request.payload.body = b"\0" * size

        recv_bytes = 0

        for _ in range(request_count):
            n = 0
            for message in grpcio_benchmark.StreamingFromServer(request):
                recv_bytes += len(message.payload.body)
                n += 1
                if n >= chunk_count:
                    break

            assert n == chunk_count

        assert recv_bytes == size * request_count * chunk_count

    benchmark(perf)
