from urllib.parse import urljoin, unquote

import aiohttp
import asyncio

import grpc.experimental.aio

from sonora import protocol
from sonora.client import Multicallable


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
        return UnaryUnaryMulticallable(
            self._session, self._url, path, request_serializer, response_deserializer
        )

    def unary_stream(self, path, request_serializer, response_deserializer):
        return UnaryStreamMulticallable(
            self._session, self._url, path, request_serializer, response_deserializer
        )

    def stream_unary(self, path, request_serializer, response_deserializer):
        raise NotImplementedError()

    def stream_stream(self, path, request_serializer, response_deserializer):
        raise NotImplementedError()


class UnaryUnaryMulticallable(Multicallable):
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


class UnaryStreamMulticallable(Multicallable):
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

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if self._response:
            self._response.release()

    async def _get_response(self):
        if self._response is None:
            self._response = await self._request

            protocol.raise_for_status(self._response.headers)

        return self._response


class UnaryUnaryCall(Call):
    def __await__(self):
        response = yield from self._get_response().__await__()

        data = yield from response.read().__await__()

        try:
            if data:
                trailers, _, message = protocol.unrwap_message(data)

                if trailers:
                    raise NotImplementedError(
                        "Trailers are not supported for UnaryUnary RPCs"
                    )

                return self._deserializer(message)
        finally:
            protocol.raise_for_status(response.headers)


class UnaryStreamCall(Call):
    async def read(self):
        response = await self._get_response()

        trailer_message = None

        async for trailers, _, message in protocol.unwrap_message_stream_async(
            response.content
        ):
            if trailers:
                trailer_message = message
                break
            else:
                return self._deserializer(message)

        protocol.raise_for_status(response.headers, trailer_message)

        return grpc.experimental.aio.EOF

    async def __aiter__(self):
        response = await self._get_response()

        trailer_message = None

        async for trailers, _, message in protocol.unwrap_message_stream_async(
            response.content
        ):
            if trailers:
                trailer_message = message
                break
            else:
                yield self._deserializer(message)

        protocol.raise_for_status(response.headers, trailer_message)
