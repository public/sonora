from collections import namedtuple
from urllib.parse import quote

import grpc

from sonora import protocol
from sonora.context import gRPCContext


_HandlerCallDetails = namedtuple(
    "_HandlerCallDetails", ("method", "invocation_metadata")
)


class grpcWSGI(grpc.Server):
    """
    WSGI Application Object that understands gRPC-Web.

    This is called by the WSGI server that's handling our actual HTTP
    connections. That means we can't use the normal gRPC I/O loop etc.
    """

    def __init__(self, application=None):
        self._application = application
        self._handlers = []

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

    def _get_rpc_handler(self, environ):
        path = environ["PATH_INFO"]

        handler_call_details = _HandlerCallDetails(path, None)

        rpc_handler = None
        for handler in self._handlers:
            rpc_handler = handler.service(handler_call_details)
            if rpc_handler:
                return rpc_handler

        return None

    def _read_request(self, environ):
        try:
            content_length = environ.get("CONTENT_LENGTH")
            if content_length:
                content_length = int(content_length)
            else:
                content_length = None
        except ValueError:
            content_length = None

        stream = environ["wsgi.input"]

        transfer_encoding = environ.get("HTTP_TRANSFER_ENCODING")

        if transfer_encoding == "chunked":
            buffer = []
            line = stream.readline()

            while line:
                if not line:
                    break

                size = line.split(b";", 1)[0]

                if size == "\r\n":
                    break

                chunk_size = int(size, 16)

                if chunk_size == 0:
                    break

                buffer.append(stream.read(chunk_size + 2)[:-2])
                line = stream.readline()
            return b"".join(buffer)
        else:
            return stream.read(content_length or 5)

    def _do_grpc_request(self, rpc_method, environ, start_response):
        request_data = self._read_request(environ)

        context = gRPCContext()

        _, _, message = protocol.unrwap_message(request_data)
        request_proto = rpc_method.request_deserializer(message)

        resp = []

        try:
            if not rpc_method.request_streaming and not rpc_method.response_streaming:
                resp = [rpc_method.unary_unary(request_proto, context)]
            elif not rpc_method.request_streaming and rpc_method.response_streaming:
                resp = rpc_method.unary_stream(request_proto, context)
            else:
                raise NotImplementedError()
        except grpc.RpcError:
            pass

        headers = [
            ("Content-Type", "application/grpc-web+proto"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Expose-Headers", "*"),
        ]

        # For unary responses we need to immediately set the status headers.

        if not rpc_method.response_streaming:
            headers.append(("grpc-status", str(context.code.value[0])))
            if context.details:
                headers.append(("grpc-message", quote(context.details)))

        start_response(_grpc_status_to_wsgi_status(context.code), headers)

        for message in resp:
            yield protocol.wrap_message(
                False, False, rpc_method.response_serializer(message)
            )

        # For streaming responses only send the status header as a trailer.

        if rpc_method.response_streaming:
            trailers = [("grpc-status", str(context.code.value[0]))]
            if context.details:
                trailers.append(("grpc-message", quote(context.details)))

            trailer_message = protocol.pack_trailers(trailers)

            yield protocol.wrap_message(True, False, trailer_message)

    def _do_cors_preflight(self, environ, start_response):
        start_response(
            "204 No Content",
            [
                ("Content-Type", "text/plain"),
                ("Content-Length", "0"),
                ("Access-Control-Allow-Methods", "POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "*"),
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Credentials", "true"),
                ("Access-Control-Expose-Headers", "*"),
            ],
        )
        return []

    def __call__(self, environ, start_response):
        """
        Our actual WSGI request handler. Will execute the request
        if it matches a configured gRPC service path or fall through
        to the next application.
        """

        rpc_method = self._get_rpc_handler(environ)
        request_method = environ["REQUEST_METHOD"]

        if rpc_method:
            if request_method == "POST":
                return self._do_grpc_request(rpc_method, environ, start_response)
            elif request_method == "OPTIONS":
                return self._do_cors_preflight(environ, start_response)
            else:
                start_response("400 Bad Request", [])
                return []

        if self._application:
            return self._application(environ, start_response)
        else:
            start_response("404 Not Found", [])
            return []


def _grpc_status_to_wsgi_status(code):
    if code == grpc.StatusCode.OK:
        return "200 OK"
    elif code is None:
        return "200 OK"
    elif code == grpc.StatusCode.UNKNOWN:
        return "500 Internal Server Error"
    elif code == grpc.StatusCode.INTERNAL:
        return "500 Internal Server Error"
    elif code == grpc.StatusCode.UNAVAILABLE:
        return "503 Service Unavailable"
    elif code == grpc.StatusCode.INVALID_ARGUMENT:
        return "400 Bad Request"
    elif code == grpc.StatusCode.UNIMPLEMENTED:
        return "404 Not Found"
    elif code == grpc.StatusCode.PERMISSION_DENIED:
        return "403 Forbidden"
    else:
        return "500 Internal Server Error"
