import functools
import inspect
from urllib.parse import urljoin

import grpc
import requests

from sonora import protocol


def insecure_web_channel(url):
    return WebChannel(url)


class WebChannel:
    def __init__(self, url):
        if not url.startswith("http") and "://" not in url:
            url = f"http://{url}"

        self._url = url
        self._session = requests.Session()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._session.close()

    def unary_unary(self, path, request_serializer, response_deserializer):
        return UnaryUnaryMulticallable(
            self._session, self._url, path, request_serializer, response_deserializer
        )

    def unary_stream(self, path, request_serializer, response_deserializer):
        return UnaryStreamMulticallable(
            self._session, self._url, path, request_serializer, response_deserializer
        )

    def stream_unary(self, path, request_serializer, response_deserializer):
        return NotImplementedMulticallable()

    def stream_stream(self, path, request_serializer, response_deserializer):
        return NotImplementedMulticallable()


class Multicallable:
    def __init__(self, session, url, path, request_serializer, request_deserializer):
        self._session = session

        self._url = url
        self._path = path
        self._rpc_url = urljoin(url, path)

        self._headers = {"x-user-agent": "grpc-web-python/0.1"}

        self._serializer = request_serializer
        self._deserializer = request_deserializer

    def future(self, request):
        raise NotImplementedError()


class NotImplementedMulticallable(Multicallable):
    def __init__(self):
        pass

    def __call__(self, request, timeout=None):
        def nope(*args, **kwargs):
            raise NotImplementedError()

        return nope


class UnaryUnaryMulticallable(Multicallable):
    def __call__(self, request, timeout=None):
        return UnaryUnaryCall(
            request,
            timeout,
            self._headers,
            self._rpc_url,
            self._session,
            self._serializer,
            self._deserializer,
        )()


class UnaryStreamMulticallable(Multicallable):
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


class Call:
    def __init__(
        self, request, timeout, metadata, url, session, serializer, deserializer
    ):
        self._request = request
        self._timeout = timeout
        self._metadata = metadata
        self._url = url
        self._session = session
        self._serializer = serializer
        self._deserializer = deserializer
        self._response = None

        if timeout is not None:
            self._metadata["grpc-timeout"] = protocol.serialize_timeout(timeout)

    @classmethod
    def _raise_timeout(cls, exc):
        def decorator(func):
            if inspect.isasyncgenfunction(func):

                async def wrapper(self, *args, **kwargs):
                    try:
                        async for result in func(self, *args, **kwargs):
                            yield result
                    except exc:
                        raise protocol.WebRpcError(
                            grpc.StatusCode.DEADLINE_EXCEEDED,
                            "request timed out at the client",
                        )

            elif inspect.iscoroutinefunction(func):

                async def wrapper(self, *args, **kwargs):
                    try:
                        return await func(self, *args, **kwargs)
                    except exc:
                        raise protocol.WebRpcError(
                            grpc.StatusCode.DEADLINE_EXCEEDED,
                            "request timed out at the client",
                        )

            elif inspect.isgeneratorfunction(func):

                def wrapper(self, *args, **kwargs):
                    try:
                        result = yield from func(self, *args, **kwargs)
                        return result
                    except exc:
                        raise protocol.WebRpcError(
                            grpc.StatusCode.DEADLINE_EXCEEDED,
                            "request timed out at the client",
                        )

            else:

                def wrapper(self, *args, **kwargs):
                    try:
                        return func(self, *args, **kwargs)
                    except exc:
                        raise protocol.WebRpcError(
                            grpc.StatusCode.DEADLINE_EXCEEDED,
                            "request timed out at the client",
                        )

            return functools.wraps(func)(wrapper)

        return decorator


class UnaryUnaryCall(Call):
    @Call._raise_timeout(requests.exceptions.Timeout)
    def __call__(self):
        with self._session.post(
            self._url,
            data=protocol.wrap_message(False, False, self._serializer(self._request)),
            headers=self._metadata,
            timeout=self._timeout,
        ) as self._response:
            protocol.raise_for_status(self._response.headers)
            trailers, _, message = protocol.unrwap_message(self._response.content)
            assert not trailers
            return self._deserializer(message)


class UnaryStreamCall(Call):
    @Call._raise_timeout(requests.exceptions.Timeout)
    def __iter__(self):
        with self._session.post(
            self._url,
            data=protocol.wrap_message(False, False, self._serializer(self._request)),
            headers=self._metadata,
            timeout=self._timeout,
            stream=True,
        ) as self._response:
            for trailers, _, message in protocol.unwrap_message_stream(
                self._response.raw
            ):
                if trailers:
                    break
                else:
                    yield self._deserializer(message)

            protocol.raise_for_status(
                self._response.headers, message if trailers else None
            )
