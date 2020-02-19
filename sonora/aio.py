from urllib.parse import urljoin, unquote

import aiohttp
import asyncio

import grpc.experimental.aio

from sonora import protocol
from sonora.client import WebRpcError


def insecure_web_channel(url):
    return WebChannel(url)


class WebChannel:
    def __init__(self, url):
        self._url = url
        self._session = aiohttp.ClientSession()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, exception_value, traceback):
        await self._session.close()

    def __await__(self):
        yield self

    def unary_unary(self, path, request_serializer, response_deserializer):
        return UnaryUnary(
            self._session, self._url, path, request_serializer, response_deserializer
        )

    def unary_stream(self, path, request_serializer, response_deserializer):
        return UnaryStream(
            self._session, self._url, path, request_serializer, response_deserializer
        )

    def stream_unary(self, path, request_serializer, response_deserializer):
        raise NotImplementedError()

    def stream_stream(self, path, request_serializer, response_deserializer):
        raise NotImplementedError()


class UnaryUnary:
    def __init__(self, session, url, path, request_serializer, request_deserializer):
        self._session = session
        self._url = url
        self._path = path
        self._serializer = request_serializer
        self._deserializer = request_deserializer

    def future(self, request):
        raise NotImplementedError()

    def __call__(self, request, timeout=None):
        url = urljoin(self._url, self._path)

        headers = {"x-user-agent": "grpc-web-python/0.1"}

        request = self._session.post(
            url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
        )

        return UnaryUnaryCall(request, self._deserializer)


class UnaryStream:
    def __init__(self, session, url, path, request_serializer, request_deserializer):
        self._session = session
        self._url = url
        self._path = path
        self._serializer = request_serializer
        self._deserializer = request_deserializer

    def future(self, request):
        raise NotImplementedError()

    def __call__(self, request, timeout=None):
        url = urljoin(self._url, self._path)

        headers = {"x-user-agent": "grpc-web-python/0.1"}

        request = self._session.post(
            url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
        )

        return UnaryStreamCall(request, self._deserializer)


class Call:
    def __init__(self, request, deserializer):
        self._request = request
        self._deserializer = deserializer
        
        self._response = None
        self._iter = None

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if self._response:
            self._response.release()


class UnaryUnaryCall(Call):
    def __await__(self):
        if self._response is None:
            self._response = yield from self._request.__await__()
            self._iter = _iter_resp(self._response)

        message = yield from self._iter.__anext__().__await__()

        try:
            trailers = yield from self._iter.__anext__().__await__()
        except StopAsyncIteration:
            return self._deserializer(message)
        else:
            raise ValueError("Failed to consume entire response stream for UnaryUnary!?")


class UnaryStreamCall(Call):
    async def read(self):
        if self._response is None:
            self._response = await self._request
            self._iter = _iter_resp(self._response)

        try:
            return self._deserializer(await self._iter.__anext__())
        except StopAsyncIteration:
            return grpc.experimental.aio.EOF
            

    async def __aiter__(self):
        if self._response is None:
            self._response = await self._request
            self._iter = _iter_resp(self._response)

        async for message in self._iter:
            yield self._deserializer(message)


async def _iter_resp(resp):
    trailer_message = None

    try:
        async for trailers, _, message in protocol.unwrap_message_stream_async(
            resp.content
        ):
            if trailers:
                trailer_message = message
                break
            else:
                yield message
    except asyncio.IncompleteReadError:
        pass

    if trailer_message:
        metadata = dict(protocol.unpack_trailers(trailer_message))
    else:
        metadata = resp.headers.copy()

    if "grpc-message" in metadata:
        metadata["grpc-message"] = unquote(metadata["grpc-message"])

    if metadata["grpc-status"] != "0":
        raise WebRpcError.from_metadata(metadata)
