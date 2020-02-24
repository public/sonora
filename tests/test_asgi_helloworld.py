import grpc
import pytest

from google.protobuf.empty_pb2 import Empty
from tests import helloworld_pb2


@pytest.mark.asyncio
async def test_helloworld_sayhello(asgi_greeter):
    for name in ("you", "world"):
        request = helloworld_pb2.HelloRequest(name=name)
        response = await asgi_greeter.SayHello(request)
        assert response.message != name
        assert name in response.message


@pytest.mark.asyncio
async def test_helloworld_unarytimeout(asgi_greeter):
    request = helloworld_pb2.TimeoutRequest(seconds=0.1)
    with pytest.raises(grpc.RpcError) as exc:
        await asgi_greeter.UnaryTimeout(request, timeout=0.001)
    assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


@pytest.mark.asyncio
async def test_helloworld_streamtimeout(asgi_greeter):
    request = helloworld_pb2.TimeoutRequest(seconds=0.1)
    response = asgi_greeter.StreamTimeout(request, timeout=0.001)

    with pytest.raises(grpc.RpcError) as exc:
        async for r in response:
            pass
    assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


@pytest.mark.asyncio
async def test_helloworld_sayhelloslowly(asgi_greeter):
    for name in ("you", "world"):
        request = helloworld_pb2.HelloRequest(name=name)
        response = asgi_greeter.SayHelloSlowly(request)
        message = "".join([r.message async for r in response])
        assert message != name
        assert name in message


@pytest.mark.asyncio
async def test_helloworld_abort(asgi_greeter):
    with pytest.raises(grpc.RpcError) as exc:
        await asgi_greeter.Abort(Empty())

    assert exc.value.code() == grpc.StatusCode.ABORTED
    assert exc.value.details() == "test aborting"
