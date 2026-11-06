"""Bounded local pipe framing shared by SuiteBridge endpoints.

The endpoints independently validate message identity, sequence and lifecycle.
Test output must never be written to these protocol descriptors.
"""
import json
import os
import struct

SCHEMA_VERSION = 1
MAX_FRAME_BYTES = 1024 * 1024


class ProtocolError(ValueError):
    pass


def _read_exact(fd, amount):
    chunks = bytearray()
    while len(chunks) < amount:
        try:
            part = os.read(fd, amount - len(chunks))
        except InterruptedError:
            continue
        if not part:
            label = 'EOF' if not chunks else 'partial frame followed by EOF'
            raise ProtocolError(label)
        chunks.extend(part)
    return bytes(chunks)


def read_frame(fd):
    size, = struct.unpack('!I', _read_exact(fd, 4))
    if not 0 < size <= MAX_FRAME_BYTES:
        raise ProtocolError('frame length outside 1..1048576 bytes')
    payload = _read_exact(fd, size)
    try:
        value = json.loads(payload.decode('utf-8'),
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ProtocolError('frame is not finite UTF-8 JSON') from error
    if not isinstance(value, dict):
        raise ProtocolError('frame must contain a JSON object')
    return value


def write_frame(fd, message):
    if not isinstance(message, dict):
        raise ProtocolError('frame must contain a JSON object')
    try:
        payload = json.dumps(message, ensure_ascii=True, allow_nan=False,
                             separators=(',', ':')).encode('utf-8')
    except (ValueError, TypeError, RecursionError) as error:
        raise ProtocolError('message is not finite JSON') from error
    if not 0 < len(payload) <= MAX_FRAME_BYTES:
        raise ProtocolError('frame length outside 1..1048576 bytes')
    remaining = memoryview(struct.pack('!I', len(payload)) + payload)
    while remaining:
        try:
            written = os.write(fd, remaining)
        except InterruptedError:
            continue
        if written <= 0:
            raise ProtocolError('protocol write made no progress')
        remaining = remaining[written:]
