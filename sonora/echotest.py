from google.protobuf.duration_pb2 import Duration
import sonora.client
from echo.echo import echo_pb2_grpc, echo_pb2

c = sonora.client.insecure_web_channel("http://localhost:8888")
x = echo_pb2_grpc.EchoServiceStub(c)
d = Duration(seconds=1)

for r in x.ServerStreamingEcho(
    echo_pb2.ServerStreamingEchoRequest(
        message="honk", message_count=10, message_interval=d
    )
):
    print(r)
