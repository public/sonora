import asyncio
from concurrent import futures
import contextlib
import multiprocessing
import socket
import time

import bjoern
import grpc
from google.protobuf import empty_pb2
import pytest
import uvicorn

import sonora.aio
import sonora.asgi
import sonora.client
import sonora.protocol
import sonora.wsgi

from tests import benchmark_pb2, benchmark_pb2_grpc, helloworld_pb2, helloworld_pb2_grpc

FORMAT_STRING = "Hello, {request.name}!"


class SyncGreeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        return helloworld_pb2.HelloReply(message=FORMAT_STRING.format(request=request))

    def SayHelloSlowly(self, request, context):
        message = FORMAT_STRING.format(request=request)
        for char in message:
            yield helloworld_pb2.HelloReply(message=char)

    def Abort(self, request, context):
        context.abort(grpc.StatusCode.ABORTED, "test aborting")

    def UnaryTimeout(self, request, context):
        while 1:
            time.sleep(request.seconds)

    def StreamTimeout(self, request, context):
        while 1:
            time.sleep(request.seconds)
            yield empty_pb2.Empty()

    def HelloMetadata(self, request, context):
        for key, value in context.invocation_metadata():
            if key == request.name:
                break
        else:
            raise KeyError(request.name)

        return helloworld_pb2.HelloReply(message=repr(value))


class AsyncGreeter(helloworld_pb2_grpc.GreeterServicer):
    async def SayHello(self, request, context):
        return helloworld_pb2.HelloReply(message=FORMAT_STRING.format(request=request))

    async def SayHelloSlowly(self, request, context):
        message = FORMAT_STRING.format(request=request)

        for char in message:
            yield helloworld_pb2.HelloReply(message=char)

    async def Abort(self, request, context):
        await context.abort(grpc.StatusCode.ABORTED, "test aborting")

    async def UnaryTimeout(self, request, context):
        while 1:
            await asyncio.sleep(request.seconds)

    async def StreamTimeout(self, request, context):
        while 1:
            await asyncio.sleep(request.seconds)
            yield empty_pb2.Empty()

    async def HelloMetadata(self, request, context):
        for key, value in context.invocation_metadata():
            if key == request.name:
                break
        else:
            raise KeyError(request.name)

        return helloworld_pb2.HelloReply(message=repr(value))


class SyncBenchmark(benchmark_pb2_grpc.BenchmarkServiceServicer):
    def UnaryCall(self, request, context):
        response = benchmark_pb2.SimpleResponse()
        response.payload.body = b"\0" * request.response_size
        return response

    def StreamingCall(self, request, context):
        raise NotImplementedError()

    def StreamingFromClient(self, request, context):
        raise NotImplementedError()

    def StreamingFromServer(self, request, context):
        response = benchmark_pb2.SimpleResponse()
        response.payload.body = request.payload.body
        while 1:
            yield response

    def StreamingBothWays(self, request, context):
        raise NotImplementedError()


class AsyncBenchmark(benchmark_pb2_grpc.BenchmarkServiceServicer):
    async def UnaryCall(self, request, context):
        response = benchmark_pb2.SimpleResponse()
        response.payload.body = b"\0" * request.response_size
        return response

    async def StreamingCall(self, request, context):
        raise NotImplementedError()

    async def StreamingFromClient(self, request, context):
        raise NotImplementedError()

    async def StreamingFromServer(self, request, context):
        response = benchmark_pb2.SimpleResponse()
        response.payload.body = request.payload.body
        while 1:
            yield response

    async def StreamingBothWays(self, request, context):
        raise NotImplementedError()


def _asgi_helloworld_server(lock, port):
    grpc_asgi_app = sonora.asgi.grpcASGI()
    helloworld_pb2_grpc.add_GreeterServicer_to_server(AsyncGreeter(), grpc_asgi_app)

    lock.release()

    uvicorn.run(
        grpc_asgi_app, host="127.0.0.1", port=port, log_level="info", access_log=False
    )


def _asgi_benchmark_server(lock, port):
    grpc_asgi_app = sonora.asgi.grpcASGI()
    benchmark_pb2_grpc.add_BenchmarkServiceServicer_to_server(
        AsyncBenchmark(), grpc_asgi_app
    )

    lock.release()

    uvicorn.run(
        grpc_asgi_app, host="127.0.0.1", port=port, log_level="info", access_log=False
    )


def _wsgi_helloworld_server(lock, port):
    grpc_wsgi_app = sonora.wsgi.grpcWSGI(None)
    helloworld_pb2_grpc.add_GreeterServicer_to_server(SyncGreeter(), grpc_wsgi_app)
    bjoern.listen(grpc_wsgi_app, "localhost", port)

    lock.release()

    bjoern.run()


def _wsgi_benchmark_server(lock, port):
    grpc_wsgi_app = sonora.wsgi.grpcWSGI(None)
    benchmark_pb2_grpc.add_BenchmarkServiceServicer_to_server(
        SyncBenchmark(), grpc_wsgi_app
    )
    bjoern.listen(grpc_wsgi_app, "localhost", port)

    lock.release()

    bjoern.run()


def _grpcio_benchmark_server(lock, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    benchmark_pb2_grpc.add_BenchmarkServiceServicer_to_server(SyncBenchmark(), server)
    server.add_insecure_port(f"localhost:{port}")

    lock.release()

    server.start()
    server.wait_for_termination()


def _wait_for_server(port, timeout=5):
    start = time.time()

    while time.time() - start < timeout:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(("127.0.0.1", int(port)))
        except ConnectionRefusedError:
            continue
        else:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            return

    raise ConnectionRefusedError("Unable to connect to test server. Did it start OK?")


def _server_fixture(server):
    def fixture(unused_port_factory):
        lock = multiprocessing.Lock()
        lock.acquire()

        port = unused_port_factory()

        server_proc = multiprocessing.Process(target=server, args=(lock, port))
        server_proc.start()

        lock.acquire()

        _wait_for_server(port)

        yield port

        assert server_proc.is_alive()

        server_proc.kill()
        server_proc.join()

    return fixture


def _sync_channel_fixture(server, channel, stub):
    def fixture(unused_port_factory):
        make_server = contextlib.contextmanager(_server_fixture(server))
        with make_server(unused_port_factory) as port:
            with channel(f"localhost:{port}") as chan:
                yield stub(chan)

    return fixture


def _async_channel_fixture(server, channel, stub):
    async def fixture(unused_port_factory):
        make_server = contextlib.contextmanager(_server_fixture(server))
        with make_server(unused_port_factory) as port:
            async with channel(f"localhost:{port}") as chan:
                yield stub(chan)

    return fixture


asgi_greeter_server = pytest.fixture(_server_fixture(_asgi_helloworld_server))
wsgi_greeter_server = pytest.fixture(_server_fixture(_wsgi_helloworld_server))

asgi_benchmark_server = pytest.fixture(_server_fixture(_asgi_benchmark_server))
grpcio_benchmark_server = pytest.fixture(_server_fixture(_grpcio_benchmark_server))
wsgi_benchmark_server = pytest.fixture(_server_fixture(_wsgi_benchmark_server))

wsgi_greeter = pytest.fixture(
    _sync_channel_fixture(
        _wsgi_helloworld_server,
        sonora.client.insecure_web_channel,
        helloworld_pb2_grpc.GreeterStub,
    )
)
asgi_greeter = pytest.fixture(
    _async_channel_fixture(
        _asgi_helloworld_server,
        sonora.aio.insecure_web_channel,
        helloworld_pb2_grpc.GreeterStub,
    )
)

asgi_benchmark = pytest.fixture(
    _async_channel_fixture(
        _asgi_benchmark_server,
        sonora.aio.insecure_web_channel,
        benchmark_pb2_grpc.BenchmarkServiceStub,
    )
)
wsgi_benchmark = pytest.fixture(
    _sync_channel_fixture(
        _wsgi_benchmark_server,
        sonora.client.insecure_web_channel,
        benchmark_pb2_grpc.BenchmarkServiceStub,
    )
)
grpcio_benchmark = pytest.fixture(
    _sync_channel_fixture(
        _grpcio_benchmark_server,
        grpc.insecure_channel,
        benchmark_pb2_grpc.BenchmarkServiceStub,
    )
)
