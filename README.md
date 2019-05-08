[![CircleCI](https://circleci.com/gh/public/grpcWSGI.svg?style=svg)](https://circleci.com/gh/public/grpcWSGI)

# gRPC-WSGI

A gRPC-Web implementation based on Python's WSGI standard.

## Why?

gRPC has a lot going for it but is awkward to use in some environments. gRPC-WSGI makes it easy to integrate gRPC when you need to use HTTP/1.1 load balancers or proxies, or want to integrate gRPC into existing services such as Django or Flask apps that speak a different protocol most of the time.

There are two main capabilities this implementation has over Google's.

 1. HTTP/1.1 compatability via gRPC-Web, even for unary_stream RPCs using protobuf. Without the need for a sidecar proxy process like Envoy.
 2. Run gRPC and other HTTP stuff on the same socket.

## How?

gRPC-WSGI is designed to require minimal changes to an existing WSGI or gRPC code base.

### Server

Normally a WSGI application (such as your favourite Django app) will call something such as 

```python
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

in it somewhere so that your application server (uWSGI, Gunicorn etc) knows where your code is.

To add gRPC-WSGI to an application like the above all you need to do to enable it is this.

```python
from django.core.wsgi import get_wsgi_application
from grpcWSGI.server import grpcWSGI

application = get_wsgi_application()
application = grpcWSGI(application)
```

The grpcWSGI application object also happens to be compatible with the normal grpc.Server interface.
So all you need to do actually attach your RPCs and start making calls to your new service is the usual gRPC setup of e.g.

```python
helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), application)
```

And now you have a combined HTTP/1.1 Django + gRPC application all under a single port.

### Client

Setting up a client is similarly very simple and similar to standard gRPC calls.

Instead of using gRPCs native `insecure_channel` API we have `grpcWSGI.client.insecure_web_channel` instead which provides a https://github.com/kennethreitz/requests powered client channel to a gRPC-Web server. e.g.

```python
    import gRPCWSGI.client
    
    with grpcWSGI.client.insecure_web_channel(
        f"http://localhost:8080"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        print(stub.SayHello("world"))
```

# TODO

 * Error handling
 * Compression?
 * Benchmarks?
 * Clean up the CORS stuff.
 * StreamStream/StreamUnary RPCs?
 * Retries, caching and other client options.
 * Quality of life integrations for Django, Flask etc.
 * application/grpc-web-text support? Do I care about IE10? JSON is potentially faster than Protobuf sometimes...
 * aiohttp / grpc-aiohttp / ASGI integration?
 * MyPy annotations? https://github.com/dropbox/mypy-protobuf Already makes this pretty OK.
 * Use more of the ABCs and other standard stuff from the grpc package
 * Make support for chunked encoding vaguely reliable
 * Some kind of metaclass magic to make it easier to ensure you've actually implemented a servers interface
