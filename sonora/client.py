import os
from urllib.parse import urljoin, unquote

import grpc
import requests

from sonora import protocol


def insecure_web_channel(url):
    return WebChannel(url)


def _iter_resp(resp):
    trailer_message = None

    for trailers, _, message in protocol.unwrap_message_stream(resp.raw):
        if trailers:
            trailer_message = message
            break
        else:
            yield message

    if trailer_message:
        metadata = dict(protocol.unpack_trailers(trailer_message))
    else:
        metadata = resp.headers

    if "grpc-message" in metadata:
        metadata["grpc-message"] = unquote(metadata["grpc-message"])

    if metadata["grpc-status"] != "0":
        raise WebRpcError.from_metadata(metadata)


class WebChannel:
    def __init__(self, url):
        self._url = url
        self._session = requests.Session()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._session.close()

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

        with self._session.post(
            url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
            stream=True,
        ) as resp:
            messages = list(_iter_resp(resp))
            return self._deserializer(messages[0])


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

        with self._session.post(
            url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
            stream=True,
        ) as resp:
            for message in _iter_resp(resp):
                yield self._deserializer(message)


class WebRpcError(grpc.RpcError):
    _code_to_enum = {code.value[0]: code for code in grpc.StatusCode}

    def __init__(self, code, details, *args, **kwargs):
        super(WebRpcError, self).__init__(*args, **kwargs)

        self._code = code
        self._details = details

    @classmethod
    def from_metadata(cls, trailers):
        status = int(trailers["grpc-status"])
        details = trailers.get("grpc-message")

        code = cls._code_to_enum[status]

        return cls(code, details)

    def __str__(self):
        return "WebRpcError(status_code={}, details='{}')".format(
            self._code, self._details
        )

    def code(self):
        return self._code

    def details(self):
        return self._details
