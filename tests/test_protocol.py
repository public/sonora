import io

import pytest
from sonora import protocol


def test_wrapping():
    data = b"foobar"
    wrapped = protocol.wrap_message(False, False, data)
    assert protocol.unwrap_message(wrapped) == (False, False, data)


def test_unwrapping_stream():
    buffer = io.BytesIO()

    messages = [
        b"Tyger Tyger, burning bright,",
        b"In the forests of the night;",
        b"What immortal hand or eye,",
        b"Could frame thy fearful symmetry?",
    ]
    for message in messages:
        buffer.write(protocol.wrap_message(False, False, message))

    buffer.seek(0)

    resp_messages = []
    for _, _, resp in protocol.unwrap_message_stream(buffer):
        resp_messages.append(resp)

    assert resp_messages == messages


@pytest.mark.asyncio
async def test_unwrapping_asgi():
    messages = [
        b"Tyger Tyger, burning bright,",
        b"In the forests of the night;",
        b"What immortal hand or eye,",
        b"Could frame thy fearful symmetry?",
    ]

    buffer = [protocol.wrap_message(False, False, message) for message in messages]

    async def receive():
        return {
            "type": "http.request",
            "body": buffer.pop(0),
            "more_body": bool(buffer),
        }

    resp_messages = []
    async for _, _, resp in protocol.unwrap_message_asgi(receive):
        resp_messages.append(resp)

    assert resp_messages == messages


def test_parse_timeout():
    seconds = protocol.parse_timeout(b"100n")
    assert seconds - 0.0000001 < 0.0000001
