[![CircleCI](https://circleci.com/gh/public/grpcWSGI.svg?style=svg)](https://circleci.com/gh/public/grpcWSGI)

# gRPC-WSGI

A gRPC-Web implementation based on Python's WSGI standard.

## Why?

gRPC has a lot going for it but is awkward to use in some environments. gRPC-WSGI makes it easy to integrate gRPC when you need to use HTTP/1.1 load balancers or proxies, or want to integrate gRPC into existing services such as Django or Flask apps that speak a different protocol most of the time.

There are two main capabilities this implementation has over Google's.

 1. HTTP/1.1 compatability via gRPC-Web, even for unary_stream RPCs using protobuf. Without the need for a sidecar proxy process like Envoy.
 2. Run gRPC and other HTTP stuff on the same socket.

# TODO

 * Error handling
 * Compression?
 * Benchmarks?
 * StreamStream/StreamUnary RPCs?
 * Retries, caching and other client options.
 * Interop with Google's gRPC-Web implementation.
 * Quality of life integrations for Django, Flask etc.
 * application/grpc-web-text support? Do I care about IE10?
 * aiohttp / grpc-aiohttp integration?
