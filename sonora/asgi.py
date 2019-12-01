from collections import namedtuple
from collections.abc import AsyncIterator
from urllib.parse import quote

import grpc

from sonora import protocol
from sonora.context import gRPCContext

_HandlerCallDetails = namedtuple(
    "_HandlerCallDetails", ("method", "invocation_metadata")
)


class grpcASGI(grpc.Server):
    def __init__(self, application=None):
        self._application = application
        self._handlers = []

    async def __call__(self, scope, receive, send):
        """
        Our actual ASGI request handler. Will execute the request
        if it matches a configured gRPC service path or fall through
        to the next application.
        """

        assert scope["type"] == "http"

        print(scope)

        rpc_method = self._get_rpc_handler(scope["path"])
        request_method = scope["method"]

        if rpc_method:
            if request_method == "POST":
                await self._do_grpc_request(rpc_method, scope, receive, send)
            elif request_method == "OPTIONS":
                await self._do_cors_preflight(scope, receive, send)
            else:
                await send({"type": "http.response.start", "status": 400})
                await send(
                    {"type": "http.response.body", "body": b"", "more_body": False}
                )

        elif self._application:
            await self._application(scope, receive, send)

        else:
            await send({"type": "http.response.start", "status": 404})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    def _get_rpc_handler(self, path):
        handler_call_details = _HandlerCallDetails(path, None)

        rpc_handler = None
        for handler in self._handlers:
            rpc_handler = handler.service(handler_call_details)
            if rpc_handler:
                return rpc_handler

        return None

    async def _do_grpc_request(self, rpc_method, scope, receive, send):
        context = gRPCContext()

        request_proto_iterator = (
            rpc_method.request_deserializer(message)
            async for _, _, message in protocol.unwrap_message_asgi(receive)
        )

        if not rpc_method.request_streaming and not rpc_method.response_streaming:
            method = rpc_method.unary_unary
        elif not rpc_method.request_streaming and rpc_method.response_streaming:
            method = rpc_method.unary_stream
        elif rpc_method.request_streaming and not rpc_method.response_streaming:
            method = rpc_method.stream_unary
        elif rpc_method.request_streaming and rpc_method.response_streaming:
            method = rpc_method.stream_stream
        else:
            raise NotImplementedError

        if rpc_method.request_streaming:
            coroutine = method(request_proto_iterator, context)
        else:
            request_proto = await anext(request_proto_iterator)
            coroutine = method(request_proto, context)

        headers = [
            (b"Content-Type", b"application/grpc-web+proto"),
            (b"Access-Control-Allow-Origin", b"*"),
            (b"Access-Control-Expose-Headers", b"*"),
        ]

        try:
            if rpc_method.response_streaming:
                message = await anext(coroutine)

                status = protocol.grpc_status_to_http_status(context.code)

                body = protocol.wrap_message(
                    False, False, rpc_method.response_serializer(message)
                )

                await send(
                    {
                        "type": "http.response.start",
                        "status": status,
                        "headers": headers,
                    }
                )
                await send(
                    {"type": "http.response.body", "body": body, "more_body": True}
                )

                async for message in coroutine:
                    body = protocol.wrap_message(
                        False, False, rpc_method.response_serializer(message)
                    )
                    await send(
                        {"type": "http.response.body", "body": body, "more_body": True}
                    )

                trailers = [("grpc-status", str(context.code.value[0]))]
                if context.details:
                    trailers.append(("grpc-message", quote(context.details)))
                trailer_message = protocol.pack_trailers(trailers)
                body = protocol.wrap_message(True, False, trailer_message)
                await send(
                    {"type": "http.response.body", "body": body, "more_body": False}
                )
            else:
                message = await coroutine

                status = protocol.grpc_status_to_http_status(context.code)
                headers.append((b"grpc-status", str(context.code.value[0]).encode()))
                if context.details:
                    headers.append((b"grpc-message", quote(context.details)))

                body = protocol.wrap_message(
                    False, False, rpc_method.response_serializer(message)
                )

                await send(
                    {
                        "type": "http.response.start",
                        "status": status,
                        "headers": headers,
                    }
                )
                await send(
                    {"type": "http.response.body", "body": body, "more_body": False}
                )
        except grpc.RpcError:
            status = protocol.grpc_status_to_http_status(context.code)
            headers.append((b"grpc-status", str(context.code.value[0]).encode()))
            if context.details:
                headers.append((b"grpc-message", quote(context.details).encode()))
            await send(
                {"type": "http.response.start", "status": status, "headers": headers}
            )
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def _do_cors_preflight(self, scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"Content-Type", b"text/plain"),
                    (b"Content-Length", b"0"),
                    (b"Access-Control-Allow-Methods", b"POST, OPTIONS"),
                    (b"Access-Control-Allow-Headers", b"*"),
                    (b"Access-Control-Allow-Origin", b"*"),
                    (b"Access-Control-Allow-Credentials", b"true"),
                    (b"Access-Control-Expose-Headers", b"*"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    def add_generic_rpc_handlers(self, handlers):
        self._handlers.extend(handlers)

    def add_insecure_port(self, port):
        raise NotImplementedError()

    def add_secure_port(self, port):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


# Copied from https://github.com/python/cpython/pull/8895


_NOT_PROVIDED = object()


async def anext(async_iterator, default=_NOT_PROVIDED):
    """anext(async_iterator[, default])
    Return the next item from the async iterator.
    If default is given and the iterator is exhausted,
    it is returned instead of raising StopAsyncIteration.
    """
    if not isinstance(async_iterator, AsyncIterator):
        raise TypeError(f"anext expected an AsyncIterator, got {type(async_iterator)}")
    anxt = async_iterator.__anext__
    try:
        return await anxt()
    except StopAsyncIteration:
        if default is _NOT_PROVIDED:
            raise
        return default
