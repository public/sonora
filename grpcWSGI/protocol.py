import struct


_HEADER_FORMAT = ">BI"
_HEADER_LENGTH = struct.calcsize(_HEADER_FORMAT)


def wrap_message(compressed, message):
    return struct.pack(_HEADER_FORMAT, 1 if compressed else 0, len(message)) + message


def unrwap_message(message):
    compressed, length = struct.unpack(_HEADER_FORMAT, message[:_HEADER_LENGTH])
    data = message[_HEADER_LENGTH : _HEADER_LENGTH + length]

    if length != len(data):
        raise ValueError()

    return bool(compressed), data


def unwrap_message_stream(stream):

    data = stream.read(_HEADER_LENGTH)

    while data:
        compressed, length = struct.unpack(_HEADER_FORMAT, data)

        yield compressed, stream.read(length)

        data = stream.read(_HEADER_LENGTH)
