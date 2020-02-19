from urllib.parse import urljoin, unquote

import aiohttp
import asyncio

from sonora import protocol
from sonora.client import WebRpcError


def insecure_web_channel(url):
    return WebChannel(url)


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

    async def __call__(self, request, timeout=None):
        url = urljoin(self._url, self._path)

        headers = {"x-user-agent": "grpc-web-python/0.1"}

        async with self._session.post(
            url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
        ) as resp:
            async for message in _iter_resp(resp):
                return self._deserializer(message)


class UnaryStream:
    def __init__(self, session, url, path, request_serializer, request_deserializer):
        self._session = session
        self._url = url
        self._path = path
        self._serializer = request_serializer
        self._deserializer = request_deserializer

    def future(self, request):
        raise NotImplementedError()

    async def __call__(self, request, timeout=None):
        url = urljoin(self._url, self._path)

        headers = {"x-user-agent": "grpc-web-python/0.1"}

        async with self._session.post(
            url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
        ) as resp:
            async for message in _iter_resp(resp):
                yield self._deserializer(message)
