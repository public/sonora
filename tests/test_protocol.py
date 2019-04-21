import io

from grpcWSGI import protocol


def test_wrapping():
    data = b"foobar"
    wrapped = protocol.wrap_message(False, data)
    assert protocol.unrwap_message(wrapped) == (False, data)


def test_unwrapping_stream():
    buffer = io.BytesIO()

    messages = [
        b"Tyger Tyger, burning bright,",
        b"In the forests of the night;",
        b"What immortal hand or eye,",
        b"Could frame thy fearful symmetry?",
    ]
    for message in messages:
        buffer.write(protocol.wrap_message(False, message))
    
    buffer.seek(0)
    
    resp_messages = []
    for _, resp in protocol.unwrap_message_stream(buffer):
        resp_messages.append(resp)

    assert resp_messages == messages