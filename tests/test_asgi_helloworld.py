import multiprocessing
import os
import time

import sonora.client
import sonora.asgi

from daphne.cli import ASGI3Middleware
import daphne.server

import grpc
from google.protobuf.empty_pb2 import Empty
import pytest

from tests import helloworld_pb2
from tests import helloworld_pb2_grpc


FORMAT_STRING = "Hello, {request.name}!"


def _asgi_application():
    class Greeter(helloworld_pb2_grpc.GreeterServicer):
        async def SayHello(self, request, context):
            return helloworld_pb2.HelloReply(
                message=FORMAT_STRING.format(request=request)
            )

        async def SayHelloSlowly(self, request, context):
            message = FORMAT_STRING.format(request=request)
            for char in message:
                yield helloworld_pb2.HelloReply(message=char)

        async def Abort(self, request, context):
            context.abort(grpc.StatusCode.ABORTED, "test aborting")

    grpc_asgi_app = sonora.asgi.grpcASGI()
    helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), grpc_asgi_app)

    return grpc_asgi_app


application = _asgi_application()


def _server(lock, port):
    lock.release()
    os.system(f"daphne -p{port} tests.test_asgi_helloworld:application")


@pytest.fixture(scope="function")
def grpc_server(capsys, unused_port_factory):
    lock = multiprocessing.Lock()
    lock.acquire()

    port = unused_port_factory()

    print("Starting server at", port)

    with capsys.disabled():
        server_proc = multiprocessing.Process(target=_server, args=(lock, port))
        server_proc.daemon = True
        server_proc.start()

    lock.acquire()
    time.sleep(1)
    yield port
    server_proc.kill()
    server_proc.join()


def test_helloworld_sayhello(grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHello(request)
            assert response.message == FORMAT_STRING.format(request=request)


def test_helloworld_sayhelloslowly(grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHelloSlowly(request)
            message = "".join(r.message for r in response)
            assert message == FORMAT_STRING.format(request=request)


def test_helloworld_abort(grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        with pytest.raises(grpc.RpcError) as exc:
            stub.Abort(Empty())

        assert exc.value.code() == grpc.StatusCode.ABORTED
        assert exc.value.details() == "test aborting"
