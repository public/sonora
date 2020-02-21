from google.protobuf.empty_pb2 import Empty
import grpc
import pytest

import sonora.client
import sonora.protocol
import sonora.wsgi

from tests import helloworld_pb2, helloworld_pb2_grpc


def test_helloworld_sayhello(wsgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{wsgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHello(request)
            assert response.message != name
            assert name in response.message


def test_helloworld_sayhello_timeout(wsgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{wsgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        request = helloworld_pb2.HelloRequest(name="timeout")

        with pytest.raises(grpc.RpcError) as exc:
            stub.SayHello(request, timeout=0.0000001)

        assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


def test_helloworld_sayhelloslowly(wsgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{wsgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHelloSlowly(request)
            message = "".join(r.message for r in response)
            assert message != name
            assert name in message


def test_helloworld_sayhelloslowly_timeout(wsgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{wsgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        request = helloworld_pb2.HelloRequest(name="timeout")
        response = stub.SayHelloSlowly(request, timeout=0.0000001)

        with pytest.raises(grpc.RpcError) as exc:
            for r in response:
                pass
        assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


def test_helloworld_abort(wsgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{wsgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        with pytest.raises(grpc.RpcError) as exc:
            stub.Abort(Empty())

        assert exc.value.code() == grpc.StatusCode.ABORTED
        assert exc.value.details() == "test aborting"
