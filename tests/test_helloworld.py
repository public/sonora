import multiprocessing
from wsgiref.simple_server import make_server

import grpcWSGI.client
import grpcWSGI.server

import grpc
from google.protobuf.empty_pb2 import Empty
import pytest

from tests import helloworld_pb2
from tests import helloworld_pb2_grpc


FORMAT_STRING = "Hello, {request.name}!"


def _server(lock, port):
    class Greeter(helloworld_pb2_grpc.GreeterServicer):
        def SayHello(self, request, context):
            return helloworld_pb2.HelloReply(
                message=FORMAT_STRING.format(request=request)
            )

        def SayHelloSlowly(self, request, context):
            message = FORMAT_STRING.format(request=request)
            for char in message:
                yield helloworld_pb2.HelloReply(message=char)

        def Abort(self, request, context):
            context.abort(grpc.StatusCode.ABORTED, "test aborting")

    grpc_wsgi_app = grpcWSGI.server.grpcWSGI(None)

    with make_server("127.0.0.1", port, grpc_wsgi_app) as httpd:
        helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), grpc_wsgi_app)
        lock.release()
        httpd.serve_forever()


@pytest.fixture
def grpc_server(capsys, unused_port_factory):
    lock = multiprocessing.Lock()
    lock.acquire()

    port = unused_port_factory()

    with capsys.disabled():
        server_proc = multiprocessing.Process(target=_server, args=(lock, port))
        server_proc.daemon = True
        server_proc.start()

    lock.acquire()

    return port


def test_helloworld_sayhello(grpc_server):
    with grpcWSGI.client.insecure_web_channel(
        f"http://localhost:{grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHello(request)
            assert response.message == FORMAT_STRING.format(request=request)


def test_helloworld_sayhelloslowly(grpc_server):
    with grpcWSGI.client.insecure_web_channel(
        f"http://localhost:{grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHelloSlowly(request)
            message = "".join(r.message for r in response)
            assert message == FORMAT_STRING.format(request=request)


def test_helloworld_abort(grpc_server):
    with grpcWSGI.client.insecure_web_channel(
        f"http://localhost:{grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        with pytest.raises(grpc.RpcError) as exc:
            stub.Abort(Empty())

        assert exc.value.code() == grpc.StatusCode.ABORTED
        assert exc.value.details() == "test aborting"
