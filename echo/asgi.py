import sys
import time

from daphne.cli import ASGI3Middleware
import daphne.server

import grpc
import sonora.asgi

from echo import echo_pb2
from echo import echo_pb2_grpc
import asyncio


class Echo(echo_pb2_grpc.EchoServiceServicer):
    async def Echo(self, request, context):
        return echo_pb2.EchoResponse(message=request.message)

    async def EchoAbort(self, request, context):
        context.set_code(grpc.StatusCode.ABORTED)
        return echo_pb2.EchoResponse(message=request.message)

    async def ServerStreamingEcho(self, request, context):
        for _ in range(request.message_count):
            yield echo_pb2.EchoResponse(message=request.message)

            await asyncio.sleep(request.message_interval.seconds / 2)
            time.sleep(request.message_interval.seconds / 2)

    async def ServerStreamingEchoAbort(self, request, context):
        for _ in range(request.message_count // 2):
            yield echo_pb2.EchoResponse(message=request.message)
        context.set_code(grpc.StatusCode.ABORTED)


def main(args):
    grpc_asgi_app = sonora.asgi.grpcASGI()
    echo_pb2_grpc.add_EchoServiceServicer_to_server(Echo(), grpc_asgi_app)

    server = daphne.server.Server(
        ASGI3Middleware(grpc_asgi_app), ["tcp:port=8080:interface=0.0.0.0"]
    )
    server.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
