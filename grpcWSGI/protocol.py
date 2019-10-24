import struct

import grpc


_HEADER_FORMAT = ">BI"
_HEADER_LENGTH = struct.calcsize(_HEADER_FORMAT)


def _pack_header_flags(trailers, compressed):
    return (trailers << 7) | (compressed)


def _unpack_header_flags(flags):
    trailers = 1 << 7
    compressed = 1

    return bool(trailers & flags), bool(compressed & flags)


def wrap_message(trailers, compressed, message):
    return (
        struct.pack(
            _HEADER_FORMAT, _pack_header_flags(trailers, compressed), len(message)
        )
        + message
    )


def unrwap_message(message):
    flags, length = struct.unpack(_HEADER_FORMAT, message[:_HEADER_LENGTH])
    data = message[_HEADER_LENGTH : _HEADER_LENGTH + length]

    if length != len(data):
        raise ValueError()

    trailers, compressed = _unpack_header_flags(flags)

    return trailers, compressed, data


def unwrap_message_stream(stream):
    data = stream.read(_HEADER_LENGTH)

    while data:
        flags, length = struct.unpack(_HEADER_FORMAT, data)
        trailers, compressed = _unpack_header_flags(flags)

        yield trailers, compressed, stream.read(length)

        if trailers:
            break

        data = stream.read(_HEADER_LENGTH)


async def unwrap_message_asgi(receive):
    buffer = bytearray()
    waiting = False
    flags = None
    length = None

    while True:
        event = await receive()
        assert event["type"].startswith("http.")

        buffer += event["body"]

        if len(buffer) >= _HEADER_LENGTH:
            if not waiting:
                flags, length = struct.unpack(_HEADER_FORMAT, buffer[:_HEADER_LENGTH])

            if len(buffer) >= _HEADER_LENGTH + length:
                waiting = False
                data = buffer[_HEADER_LENGTH : _HEADER_LENGTH + length]
                trailers, compressed = _unpack_header_flags(flags)
                yield trailers, compressed, data
                buffer = buffer[_HEADER_LENGTH + length :]
            else:
                waiting = True

        if not event.get("more_body"):
            break


def pack_trailers(trailers):
    message = []
    for k, v in trailers:
        k = k.lower()
        message.append("{0}: {1}\r\n".format(k, v).encode("utf8"))
    return b"".join(message)


def unpack_trailers(message):
    trailers = []
    for line in message.decode("utf8").splitlines():
        k, v = line.split(":", 1)
        v = v.strip()

        trailers.append((k, v))
    return trailers


def grpc_status_to_http_status(code):
    if code == grpc.StatusCode.OK:
        return 200
    elif code is None:
        return 200
    elif code == grpc.StatusCode.UNKNOWN:
        return 500
    elif code == grpc.StatusCode.INTERNAL:
        return 500
    elif code == grpc.StatusCode.UNAVAILABLE:
        return 503
    elif code == grpc.StatusCode.INVALID_ARGUMENT:
        return 400
    elif code == grpc.StatusCode.UNIMPLEMENTED:
        return 404
    elif code == grpc.StatusCode.PERMISSION_DENIED:
        return 403
    else:
        return 500
