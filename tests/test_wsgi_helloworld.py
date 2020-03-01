from google.protobuf.empty_pb2 import Empty
import grpc
import pytest

from tests import helloworld_pb2


def test_helloworld_sayhello(wsgi_greeter):
    for name in ("you", "world"):
        request = helloworld_pb2.HelloRequest(name=name)
        response = wsgi_greeter.SayHello(request)
        assert response.message != name
        assert name in response.message


def test_helloworld_unarytimeout(wsgi_greeter):
    request = helloworld_pb2.TimeoutRequest(seconds=0.1)
    with pytest.raises(grpc.RpcError) as exc:
        wsgi_greeter.UnaryTimeout(request, timeout=0.001)
    assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


def test_helloworld_streamtimeout(wsgi_greeter):
    request = helloworld_pb2.TimeoutRequest(seconds=0.1)
    response = wsgi_greeter.StreamTimeout(request, timeout=0.001)

    with pytest.raises(grpc.RpcError) as exc:
        for _ in response:
            pass
    assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


def test_helloworld_sayhelloslowly(wsgi_greeter):
    for name in ("you", "world"):
        request = helloworld_pb2.HelloRequest(name=name)
        response = wsgi_greeter.SayHelloSlowly(request)
        message = "".join(r.message for r in response)
        assert message != name
        assert name in message


def test_helloworld_abort(wsgi_greeter):
    with pytest.raises(grpc.RpcError) as exc:
        wsgi_greeter.Abort(Empty())

    assert exc.value.code() == grpc.StatusCode.ABORTED
    assert exc.value.details() == "test aborting"


def test_helloworld_unary_metadata_ascii(wsgi_greeter):
    request = helloworld_pb2.HelloRequest(name="metadata-key")
    result, call = wsgi_greeter.HelloMetadata.with_call(
        request, metadata=[("metadata-key", "honk")]
    )
    assert repr("honk") == result.message

    initial_metadata = call.initial_metadata()
    trailing_metadata = call.trailing_metadata()

    assert dict(initial_metadata)["initial-metadata-key"] == repr("honk")
    assert dict(trailing_metadata)["trailing-metadata-key"] == repr("honk")


def test_helloworld_unary_metadata_binary(wsgi_greeter):
    request = helloworld_pb2.HelloRequest(name="metadata-key-bin")
    result, call = wsgi_greeter.HelloMetadata.with_call(
        request, metadata=[("metadata-key-bin", b"\0\1\2\3")]
    )
    assert repr(b"\0\1\2\3") == result.message

    initial_metadata = call.initial_metadata()
    trailing_metadata = call.trailing_metadata()

    assert dict(initial_metadata)["initial-metadata-key-bin"] == repr(b"\0\1\2\3")
    assert dict(trailing_metadata)["trailing-metadata-key-bin"] == repr(b"\0\1\2\3")
