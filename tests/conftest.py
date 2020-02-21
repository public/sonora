import asyncio
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
from tests import helloworld_pb2, helloworld_pb2_grpc

FORMAT_STRING = "Hello, {request.name}!"


def _asgi_application():
    class Greeter(helloworld_pb2_grpc.GreeterServicer):
        async def SayHello(self, request, context):
            if request.name == "timeout":
                await asyncio.sleep(100)

            return helloworld_pb2.HelloReply(
                message=FORMAT_STRING.format(request=request)
            )

        async def SayHelloSlowly(self, request, context):
            if request.name == "timeout":
                await asyncio.sleep(100)

            message = FORMAT_STRING.format(request=request)

            for char in message:
                yield helloworld_pb2.HelloReply(message=char)

        async def Abort(self, request, context):
            context.abort(grpc.StatusCode.ABORTED, "test aborting")

    grpc_asgi_app = sonora.asgi.grpcASGI()
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), grpc_asgi_app)

    return grpc_asgi_app


asgi_application = _asgi_application()


def _asgi_server(lock, port):
    lock.release()
    os.execvp("daphne", ["daphne", f"-p{port}", "tests.conftest:asgi_application"])


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


@pytest.fixture
def asgi_grpc_server(capsys, unused_port_factory):
    lock = multiprocessing.Lock()
    lock.acquire()

    port = unused_port_factory()

    print("Starting server at", port)

    with capsys.disabled():
        server_proc = multiprocessing.Process(target=_asgi_server, args=(lock, port))
        server_proc.daemon = True
        server_proc.start()

    lock.acquire()

    _wait_for_server(port)

    yield port

    server_proc.kill()
    server_proc.join()


def _wsgi_server(lock, port):
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


@pytest.fixture
def wsgi_grpc_server(capsys, unused_port_factory):
    lock = multiprocessing.Lock()
    lock.acquire()

    port = unused_port_factory()

    with capsys.disabled():
        server_proc = multiprocessing.Process(target=_wsgi_server, args=(lock, port))
        server_proc.daemon = True
        server_proc.start()

    lock.acquire()

    _wait_for_server(port)

    yield port

    server_proc.kill()
    server_proc.join()
