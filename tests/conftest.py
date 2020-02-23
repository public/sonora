import asyncio
from concurrent import futures
import multiprocessing
import os
import socket
import time
from wsgiref.simple_server import make_server

import grpc
import pytest
import sonora.aio
import sonora.asgi
import sonora.client
import sonora.protocol
import sonora.wsgi
from tests import benchmark_pb2, benchmark_pb2_grpc, helloworld_pb2, helloworld_pb2_grpc

FORMAT_STRING = "Hello, {request.name}!"


def _asgi_helloworld_server(lock, port):
    lock.release()
    os.execvp(
        "daphne", ["daphne", f"-p{port}", "tests.conftest:asgi_helloworld_application"]
    )


def _asgi_benchmark_server(lock, port):
    lock.release()
    os.execvp(
        "daphne",
        ["daphne", f"-p{port}", "-v0", "tests.conftest:asgi_benchmark_application"],
    )


def _wsgi_helloworld_server(lock, port):
    class Greeter(helloworld_pb2_grpc.GreeterServicer):
        def SayHello(self, request, context):
            if request.name == "timeout":
                time.sleep(100)
            return helloworld_pb2.HelloReply(
                message=FORMAT_STRING.format(request=request)
            )

        def SayHelloSlowly(self, request, context):
            if request.name == "timeout":
                time.sleep(100)

            message = FORMAT_STRING.format(request=request)
            for char in message:
                yield helloworld_pb2.HelloReply(message=char)

        def Abort(self, request, context):
            context.abort(grpc.StatusCode.ABORTED, "test aborting")

    grpc_wsgi_app = sonora.wsgi.grpcWSGI(None)

    with make_server("127.0.0.1", port, grpc_wsgi_app) as httpd:
        helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), grpc_wsgi_app)
        lock.release()
        httpd.serve_forever()


def _asgi_helloworld_application():
    class Greeter(helloworld_pb2_grpc.GreeterServicer):
        async def SayHello(self, request, context):
            if request.name == "server timeout":
                await asyncio.sleep(100)
            elif request.name == "client timeout":
                time.sleep(100)

            return helloworld_pb2.HelloReply(
                message=FORMAT_STRING.format(request=request)
            )

        async def SayHelloSlowly(self, request, context):
            if request.name == "server timeout":
                await asyncio.sleep(100)
            elif request.name == "client timeout":
                time.sleep(100)

            message = FORMAT_STRING.format(request=request)

            for char in message:
                yield helloworld_pb2.HelloReply(message=char)

        async def Abort(self, request, context):
            context.abort(grpc.StatusCode.ABORTED, "test aborting")

    grpc_asgi_app = sonora.asgi.grpcASGI()
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), grpc_asgi_app)

    return grpc_asgi_app


def _asgi_benchmark_application():
    class Benchmark(benchmark_pb2_grpc.BenchmarkServiceServicer):
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
                await asyncio.sleep(0)

        async def StreamingBothWays(self, request, context):
            raise NotImplementedError()

    grpc_asgi_app = sonora.asgi.grpcASGI()
    benchmark_pb2_grpc.add_BenchmarkServiceServicer_to_server(
        Benchmark(), grpc_asgi_app
    )

    return grpc_asgi_app


def _grpcio_benchmark_server(lock, port):
    class Benchmark(benchmark_pb2_grpc.BenchmarkServiceServicer):
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

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    benchmark_pb2_grpc.add_BenchmarkServiceServicer_to_server(Benchmark(), server)
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
            print(f"Server is ready on {port}")
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            return

    raise ConnectionRefusedError("Unable to connect to test server. Did it start OK?")


def _server_fixture(server):
    def fixture(capsys, unused_port_factory):
        lock = multiprocessing.Lock()
        lock.acquire()

        port = unused_port_factory()

        print("Starting server at", port)

        with capsys.disabled():
            server_proc = multiprocessing.Process(target=server, args=(lock, port))
            server_proc.start()

        lock.acquire()

        _wait_for_server(port)

        yield port

        assert server_proc.is_alive()

        server_proc.kill()
        server_proc.join()

    return fixture


asgi_grpc_server = pytest.fixture(_server_fixture(_asgi_helloworld_server))
wsgi_grpc_server = pytest.fixture(_server_fixture(_wsgi_helloworld_server))

asgi_benchmark_grpc_server = pytest.fixture(_server_fixture(_asgi_benchmark_server))
grpcio_benchmark_grpc_server = pytest.fixture(_server_fixture(_grpcio_benchmark_server))

asgi_helloworld_application = _asgi_helloworld_application()
asgi_benchmark_application = _asgi_benchmark_application()
