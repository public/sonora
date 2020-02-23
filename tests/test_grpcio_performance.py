import pytest
import time
import grpc

from tests import benchmark_pb2, benchmark_pb2_grpc


@pytest.mark.parametrize("size", [0, 100, 1000, 10000, 100000])
def test_grpcio_unarycall(grpcio_benchmark_grpc_server, benchmark, size):
    def perf():
        with grpc.insecure_channel(f'localhost:{grpcio_benchmark_grpc_server}') as channel:
            stub = benchmark_pb2_grpc.BenchmarkServiceStub(channel)

            request = benchmark_pb2.SimpleRequest(response_size=size)

            for _ in range(1000):
                _ = stub.UnaryCall(request)

    benchmark(perf)


@pytest.mark.parametrize("size", [0, 100, 1000, 10000, 100000])
def test_grpcio_streamingfromserver(grpcio_benchmark_grpc_server, benchmark, size):

    request_count = 10
    chunk_count = 100

    def perf():
        with grpc.insecure_channel(f'localhost:{grpcio_benchmark_grpc_server}') as channel:
            stub = benchmark_pb2_grpc.BenchmarkServiceStub(channel)

            request = benchmark_pb2.SimpleRequest(response_size=size)
            request.payload.body = b"\0" * size

            recv_bytes = 0

            for _ in range(request_count):
                n = 0
                for message in stub.StreamingFromServer(request):
                    recv_bytes += len(message.payload.body)
                    n += 1
                    if n >= chunk_count:
                        break
                
                assert n == chunk_count
            
            assert recv_bytes == size * request_count * chunk_count


    benchmark(perf)
