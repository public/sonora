from urllib.parse import urljoin

import grpc
import requests

from sonora import protocol


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


class UnaryUnaryMulticallable(Multicallable):
    def __call__(self, request, timeout=None):
        with self._session.post(
            self._rpc_url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=self._headers,
            timeout=timeout
        ) as resp:
            return UnaryUnaryCall(resp, self._deserializer)()


class UnaryStreamMulticallable(Multicallable):
    def __call__(self, request, timeout=None):
        resp = self._session.post(
            self._rpc_url,
            data=protocol.wrap_message(False, False, self._serializer(request)),
            headers=self._headers,
            timeout=timeout,
            stream=True,
        )
        
        return UnaryStreamCall(resp, self._deserializer)


class Call:
    def __init__(self, response, deserializer):
        self._response = response
        self._deserializer = deserializer

        protocol.raise_for_status(self._response.headers)



class UnaryUnaryCall(Call):
    def __call__(self):
        protocol.raise_for_status(self._response.headers)
        trailers, _, message = protocol.unrwap_message(self._response.content)
        assert not trailers
        return self._deserializer(message)


class UnaryStreamCall(Call):
    def __iter__(self):
        trailer_message = None

        for trailers, _, message in protocol.unwrap_message_stream(self._response.raw):
            if trailers:
                trailer_message = message
                break
            else:
                yield self._deserializer(message)

        self._response.close()

        protocol.raise_for_status(self._response.headers, trailer_message)
