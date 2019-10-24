import grpc

from echo import echo_pb2
from echo import echo_pb2_grpc


class Echo(echo_pb2_grpc.EchoServiceServicer):
    def Echo(self, request, context):
        return echo_pb2.EchoResponse(message=request.message)

    def EchoAbort(self, request, context):
        context.set_code(grpc.StatusCode.ABORTED)
        return echo_pb2.EchoResponse(message=request.message)

    def ServerStreamingEcho(self, request, context):
        for _ in range(request.message_count):
            yield echo_pb2.EchoResponse(message=request.message)

    def ServerStreamingEchoAbort(self, request, context):
        for _ in range(request.message_count // 2):
            yield echo_pb2.EchoResponse(message=request.message)
        context.set_code(grpc.StatusCode.ABORTED)
