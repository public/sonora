import os
from urllib.parse import urljoin

import grpc
import requests

from grpcWSGI import protocol


def insecure_web_channel(url):
    return WebChannel(url)


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

        resp = self._session.post(
            url,
            data=protocol.wrap_message(False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
        )

        if resp.status_code != 200:
            raise WebRpcError.from_response(resp)
        else:
            _, message = protocol.unrwap_message(resp.content)
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

    def __call__(self, request, timeout=None):
        url = urljoin(self._url, self._path)

        headers = {"x-user-agent": "grpc-web-python/0.1"}

        resp = self._session.post(
            url,
            data=protocol.wrap_message(False, self._serializer(request)),
            headers=headers,
            timeout=timeout,
            stream=True,
        )

        if resp.status_code != 200:
            raise WebRpcError.from_response(resp)
        else:
            for _, message in protocol.unwrap_message_stream(resp.raw):
                yield self._deserializer(message)


class WebRpcError(grpc.RpcError):
    _code_to_enum = {code.value[0]: code for code in grpc.StatusCode}

    def __init__(self, code, details, *args, **kwargs):
        super(WebRpcError, self).__init__(*args, **kwargs)

        self._code = code
        self._details = details

    @classmethod
    def from_response(cls, response):
        status = int(response.headers["grpc-status"])
        details = response.headers["grpc-message"]

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
