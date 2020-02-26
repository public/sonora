import asyncio

import aiohttp
import grpc.experimental.aio

from sonora import protocol
import sonora.client


def insecure_web_channel(url):
    return WebChannel(url)


class WebChannel:
    def __init__(self, url):
        if not url.startswith("http") and "://" not in url:
            url = f"http://{url}"

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
        return sonora.client.NotImplementedMulticallable()

    def stream_stream(self, path, request_serializer, response_deserializer):
        return sonora.client.NotImplementedMulticallable()


class UnaryUnaryMulticallable(sonora.client.Multicallable):
    def __call__(self, request, timeout=None):
        return UnaryUnaryCall(
            request,
            timeout,
            self._headers,
            self._rpc_url,
            self._session,
            self._serializer,
            self._deserializer,
        )


class UnaryStreamMulticallable(sonora.client.Multicallable):
    def __call__(self, request, timeout=None):
        return UnaryStreamCall(
            request,
            timeout,
            self._headers,
            self._rpc_url,
            self._session,
            self._serializer,
            self._deserializer,
        )


class Call(sonora.client.Call):
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if self._response:
            self._response.release()

    def __del__(self):
        if self._response:
            self._response.release()

    async def _get_response(self):
        if self._response is None:
            timeout = aiohttp.ClientTimeout(total=self._timeout)

            self._response = await self._session.post(
                self._url,
                data=protocol.wrap_message(
                    False, False, self._serializer(self._request)
                ),
                headers=self._metadata,
                timeout=timeout,
            )

            protocol.raise_for_status(self._response.headers)

        return self._response


class UnaryUnaryCall(Call):
    @Call._raise_timeout(asyncio.TimeoutError)
    def __await__(self):
        response = yield from self._get_response().__await__()

        protocol.raise_for_status(response.headers)

        data = yield from response.read().__await__()

        if data:
            trailers, _, message = protocol.unrwap_message(data)

            if trailers:
                raise NotImplementedError(
                    "Trailers are not supported for UnaryUnary RPCs"
                )

            return self._deserializer(message)


class UnaryStreamCall(Call):
    @Call._raise_timeout(asyncio.TimeoutError)
    async def read(self):
        response = await self._get_response()

        async for trailers, _, message in protocol.unwrap_message_stream_async(
            response.content
        ):
            if trailers:
                break
            else:
                return self._deserializer(message)

        protocol.raise_for_status(response.headers, message if trailers else None)

        return grpc.experimental.aio.EOF

    @Call._raise_timeout(asyncio.TimeoutError)
    async def __aiter__(self):
        response = await self._get_response()

        async for trailers, _, message in protocol.unwrap_message_stream_async(
            response.content
        ):
            if trailers:
                break
            else:
                yield self._deserializer(message)

        protocol.raise_for_status(response.headers, message if trailers else None)
