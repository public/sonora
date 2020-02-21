[![CircleCI](https://circleci.com/gh/public/sonora.svg?style=svg)](https://circleci.com/gh/public/sonora)

# Sonora

Sonora is a Python-first implementation of gRPC-Web built on top of standard Python APIs like WSGI and ASGI for easy integration.

## Why?

Regular gRPC has a lot going for it but is awkward to use in some environments. gRPC-Web makes it easy to get gRPC working in
environments that need HTTP/1.1 but the Google gRPC and gRPC-Web implementations don't like to coexist with your normal Python
frameworks like Django or Flask. Unlike [grpc/grpc](https://github.com/grpc/grpc) Sonora doesn't care what ioloop you use, this
means you can run it along side any other Python web framework in the same application!

This makes it easy to

- Add gRPC to an existing code base.
- Run gRPC behind AWS and other HTTP/1.1 load balancers.
- Integrate with other ASGI frameworks like Channels, Starlette, Quart etc.
- Integrate with other WSGI frameworks like Flask, Django etc.

The name Sonora was inspired by the [Sonoran gopher snake](https://en.wikipedia.org/wiki/Pituophis_catenifer_affinis).

![Snek](https://i.imgur.com/eqhQnlY.jpg)

## How?

Sonora is designed to require minimal changes to an existing Python application.

### Server

#### WSGI

Normally a WSGI application ([such as your favourite Django app](https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/)) will have a file somewhere named `wsgi.py`
that gets your application setup and ready for your web server of choice.

```python
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

in it somewhere so that your application server (uWSGI, Gunicorn etc) knows where your code is.

To add Sonora's gRPC-Web capabilities to an application like the above all you need to do to enable it is this.

```python
from django.core.wsgi import get_wsgi_application
from sonora.wsgi import grpcWSGI
import helloworld_pb2_grpc

# Setup your frameworks default WSGI app.

application = get_wsgi_application()

# Install the Sonora grpcWSGI middleware so we can handle requests to gRPC's paths.

application = grpcWSGI(application)

# Attach your gRPC server implementation.

helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), application)
```

And now you have a combined HTTP/1.1 Django + gRPC application all under a single port.

#### ASGI

For ASGI things are mostly the same, the example shown here integrates with [Quart](https://github.com/pgjones/quart) but it's more or less the same for other frameworks.

```python
from sonora.asgi import grpcASGI
from quart import Quart
import helloworld_pb2_grpc

# Setup your frameworks default ASGI app.

application = Quart(__name__)

# Install the Sonora grpcASGI middleware so we can handle requests to gRPC's paths.

application = grpcASGI(application)

# Attach your gRPC server implementation.

helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), application)
```

And now you have a combined HTTP/1.1 Quart + gRPC application all under a single port.

### Clients

Sonora currently only provides a sync API implementation based on requests.

#### Requests (Sync)

Instead of using gRPCs native `grpc.insecure_channel` API we have `sonora.client.insecure_web_channel` instead which provides a [requests](https://github.com/kennethreitz/requests) powered client channel to a gRPC-Web server. e.g.

```python
    import sonora.client

    with sonora.client.insecure_web_channel(
        f"http://localhost:8080"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        print(stub.SayHello("world"))
```

#### Aiohttp (Async)

Instead of `grpc.aio.insecure_channel` we have `sonora.aio.insecure_web_channel` which provides an [aiohttp](https://docs.aiohttp.org/) based asyncio compatible client for gRPC-Web. e.g.

```python
    import sonora.aio

    async with sonora.aio.insecure_web_channel(
        f"http://localhost:8080"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        print(await stub.SayHello("world"))

        stub = helloworld_pb2_grpc.GreeterStub(channel)
        async for response in stub.SayHelloSlowly("world"):
            print(response)
```

This also supports the new streaming response API introduced by [gRFC L58](https://github.com/grpc/proposal/pull/155)

```python
    import sonora.aio

    async with sonora.aio.insecure_web_channel(
        f"http://localhost:8080"
    ) as channel:
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        async with stub.SayHelloSlowly("world") as response:
            print(await response.read())
```
