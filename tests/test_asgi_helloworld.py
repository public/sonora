import grpc
import pytest

import sonora.aio
import sonora.asgi
import sonora.client

from google.protobuf.empty_pb2 import Empty
from tests import helloworld_pb2, helloworld_pb2_grpc


def test_helloworld_sayhello(asgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHello(request)
            assert response.message != name
            assert name in response.message


def test_helloworld_sayhelloslowly(asgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHelloSlowly(request)
            message = "".join(r.message for r in response)
            assert message != name
            assert name in message


def test_helloworld_abort(asgi_grpc_server):
    with sonora.client.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        with pytest.raises(grpc.RpcError) as exc:
            stub.Abort(Empty())

        assert exc.value.code() == grpc.StatusCode.ABORTED
        assert exc.value.details() == "test aborting"


@pytest.mark.asyncio
async def test_helloworld_sayhello_async(asgi_grpc_server):
    async with sonora.aio.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = await stub.SayHello(request)
            assert response.message != name
            assert name in response.message


@pytest.mark.asyncio
async def test_helloworld_sayhello_timeout_async(asgi_grpc_server):
    async with sonora.aio.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        request = helloworld_pb2.HelloRequest(name="server timeout")
        with pytest.raises(grpc.RpcError) as exc:
            await stub.SayHello(request, timeout=0.1)
        assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED
        assert exc.value.details() == "rpc timed out"


@pytest.mark.asyncio
async def test_helloworld_sayhelloslowly_async(asgi_grpc_server):
    async with sonora.aio.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        for name in ("you", "world"):
            request = helloworld_pb2.HelloRequest(name=name)
            response = stub.SayHelloSlowly(request)
            message = "".join([r.message async for r in response])
            assert message != name
            assert name in message


@pytest.mark.asyncio
async def test_helloworld_sayhelloslowly_timeout_async(asgi_grpc_server):
    async with sonora.aio.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        request = helloworld_pb2.HelloRequest(name="server timeout")
        response = stub.SayHelloSlowly(request, timeout=0.0000001)

        with pytest.raises(grpc.RpcError) as exc:
            async for r in response:
                pass
        assert exc.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED
        assert exc.value.details() == "rpc timed out"


@pytest.mark.asyncio
async def test_helloworld_abort_async(asgi_grpc_server):
    async with sonora.aio.insecure_web_channel(
        f"http://localhost:{asgi_grpc_server}"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)

        with pytest.raises(grpc.RpcError) as exc:
            await stub.Abort(Empty())

        assert exc.value.code() == grpc.StatusCode.ABORTED
        assert exc.value.details() == "test aborting"
