import sys
import time
from wsgiref.simple_server import make_server

import sonora.wsgi

from test_server import empty_pb2, messages_pb2, test_pb2_grpc

_INITIAL_METADATA_KEY = "x-grpc-test-echo-initial"
_TRAILING_METADATA_KEY = "x-grpc-test-echo-trailing-bin"
_US_IN_A_SECOND = 1000 * 1000


def _maybe_echo_metadata(servicer_context):
    """Copies metadata from request to response if it is present."""
    invocation_metadata = dict(servicer_context.invocation_metadata())
    if _INITIAL_METADATA_KEY in invocation_metadata:
        initial_metadatum = (_INITIAL_METADATA_KEY,
                             invocation_metadata[_INITIAL_METADATA_KEY])
        servicer_context.send_initial_metadata((initial_metadatum,))
    if _TRAILING_METADATA_KEY in invocation_metadata:
        trailing_metadatum = (_TRAILING_METADATA_KEY,
                              invocation_metadata[_TRAILING_METADATA_KEY])
        servicer_context.set_trailing_metadata((trailing_metadatum,))


def _maybe_echo_status_and_message(request, servicer_context):
    """Sets the response context code and details if the request asks for them"""
    if request.HasField('response_status'):
        servicer_context.set_code(request.response_status.code)
        servicer_context.set_details(request.response_status.message)


class TestServiceServicer(test_pb2_grpc.TestServiceServicer):
    def EmptyCall(self, request, context):
        _maybe_echo_metadata(context)
        return empty_pb2.Empty()

    def UnaryCall(self, request, context):
        _maybe_echo_metadata(context)
        _maybe_echo_status_and_message(request, context)
        return messages_pb2.SimpleResponse(
            payload=messages_pb2.Payload(type=messages_pb2.COMPRESSABLE,
                                         body=b'\x00' * request.response_size))

    def StreamingOutputCall(self, request, context):
        _maybe_echo_status_and_message(request, context)
        for response_parameters in request.response_parameters:
            if response_parameters.interval_us != 0:
                time.sleep(response_parameters.interval_us / _US_IN_A_SECOND)
            yield messages_pb2.StreamingOutputCallResponse(
                payload=messages_pb2.Payload(type=request.response_type,
                                             body=b'\x00' *
                                             response_parameters.size))

    def StreamingInputCall(self, request_iterator, context):
        aggregate_size = 0
        for request in request_iterator:
            if request.payload is not None and request.payload.body:
                aggregate_size += len(request.payload.body)
        return messages_pb2.StreamingInputCallResponse(
            aggregated_payload_size=aggregate_size)

    def FullDuplexCall(self, request_iterator, context):
        _maybe_echo_metadata(context)
        for request in request_iterator:
            _maybe_echo_status_and_message(request, context)
            for response_parameters in request.response_parameters:
                if response_parameters.interval_us != 0:
                    time.sleep(response_parameters.interval_us /
                               _US_IN_A_SECOND)
                yield messages_pb2.StreamingOutputCallResponse(
                    payload=messages_pb2.Payload(type=request.payload.type,
                                                 body=b'\x00' *
                                                 response_parameters.size))

    # NOTE(nathaniel): Apparently this is the same as the full-duplex call?
    # NOTE(atash): It isn't even called in the interop spec (Oct 22 2015)...
    def HalfDuplexCall(self, request_iterator, context):
        return self.FullDuplexCall(request_iterator, context)

def main(args):
    grpc_wsgi_app = sonora.wsgi.grpcWSGI(None)

    with make_server("", 8080, grpc_wsgi_app) as httpd:
        test_pb2_grpc.add_TestServiceServicer_to_server(TestServiceServicer(), grpc_wsgi_app)
        print("Server up on 0.0.0.0:8080")
        httpd.serve_forever()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
