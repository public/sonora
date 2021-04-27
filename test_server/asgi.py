import asyncio
import datetime
import sys
from wsgiref.simple_server import make_server

import sonora.asgi

import daphne.server

from test_server import empty_pb2, messages_pb2, test_pb2_grpc

_INITIAL_METADATA_KEY = "x-grpc-test-echo-initial"
_TRAILING_METADATA_KEY = "x-grpc-test-echo-trailing-bin"
_US_IN_A_SECOND = 1000 * 1000
UNARY_CALL_WITH_SLEEP_VALUE = 0.2

async def _maybe_echo_metadata(servicer_context):
    """Copies metadata from request to response if it is present."""
    invocation_metadata = dict(servicer_context.invocation_metadata())
    if _INITIAL_METADATA_KEY in invocation_metadata:
        initial_metadatum = (_INITIAL_METADATA_KEY,
                             invocation_metadata[_INITIAL_METADATA_KEY])
        await servicer_context.send_initial_metadata((initial_metadatum,))

    if _TRAILING_METADATA_KEY in invocation_metadata:
        trailing_metadatum = (_TRAILING_METADATA_KEY,
                              invocation_metadata[_TRAILING_METADATA_KEY])
        servicer_context.set_trailing_metadata((trailing_metadatum,))


async def _maybe_echo_status(request: messages_pb2.SimpleRequest,
                             servicer_context):
    """Echos the RPC status if demanded by the request."""
    if request.HasField('response_status'):
        await servicer_context.abort(request.response_status.code,
                                     request.response_status.message)


class TestServiceServicer(test_pb2_grpc.TestServiceServicer):

    async def UnaryCall(self, request, context):
        await _maybe_echo_metadata(context)
        await _maybe_echo_status(request, context)
    
        return messages_pb2.SimpleResponse(
            payload=messages_pb2.Payload(type=messages_pb2.COMPRESSABLE,
                                         body=b'\x00' * request.response_size))

    async def EmptyCall(self, request, context):
        return empty_pb2.Empty()

    async def StreamingOutputCall(
            self, request: messages_pb2.StreamingOutputCallRequest,
            unused_context):
        for response_parameters in request.response_parameters:
            if response_parameters.interval_us != 0:
                await asyncio.sleep(
                    datetime.timedelta(microseconds=response_parameters.
                                       interval_us).total_seconds())
            if response_parameters.size != 0:
                yield messages_pb2.StreamingOutputCallResponse(
                    payload=messages_pb2.Payload(type=request.response_type,
                                                 body=b'\x00' *
                                                 response_parameters.size))
            else:
                yield messages_pb2.StreamingOutputCallResponse()

    # Next methods are extra ones that are registred programatically
    # when the sever is instantiated. They are not being provided by
    # the proto file.
    async def UnaryCallWithSleep(self, unused_request, unused_context):
        await asyncio.sleep(UNARY_CALL_WITH_SLEEP_VALUE)
        return messages_pb2.SimpleResponse()

    async def StreamingInputCall(self, request_async_iterator, unused_context):
        aggregate_size = 0
        async for request in request_async_iterator:
            if request.payload is not None and request.payload.body:
                aggregate_size += len(request.payload.body)
        return messages_pb2.StreamingInputCallResponse(
            aggregated_payload_size=aggregate_size)

    async def FullDuplexCall(self, request_async_iterator, context):
        await _maybe_echo_metadata(context)
        async for request in request_async_iterator:
            await _maybe_echo_status(request, context)
            for response_parameters in request.response_parameters:
                if response_parameters.interval_us != 0:
                    await asyncio.sleep(
                        datetime.timedelta(microseconds=response_parameters.
                                           interval_us).total_seconds())
                if response_parameters.size != 0:
                    yield messages_pb2.StreamingOutputCallResponse(
                        payload=messages_pb2.Payload(type=request.payload.type,
                                                     body=b'\x00' *
                                                     response_parameters.size))
                else:
                    yield messages_pb2.StreamingOutputCallResponse()


application = sonora.asgi.grpcASGI()
test_pb2_grpc.add_TestServiceServicer_to_server(TestServiceServicer(), application)
