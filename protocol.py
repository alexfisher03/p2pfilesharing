from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from enum import IntEnum

HEADER = b"P2PFILESHARINGPROJ"
ZEROS = b"\x00" * 10
HANDSHAKE_LENGTH = 32


class MessageType(IntEnum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7


@dataclass(frozen=True)
class Message:
    message_type: MessageType
    payload: bytes = b""


# ! means big-endian (network byte order), I means unsigned 4-byte int
# Build the fixed 32-byte handshake
# [18-byte header][10 zero bytes][4-byte peer id]
def make_handshake(peer_id: int) -> bytes:
    return HEADER + ZEROS + struct.pack("!I", peer_id)


# Validate a received handshake and return the peer id inside it
def parse_handshake(data: bytes) -> int:
    if len(data) != HANDSHAKE_LENGTH:
        raise ValueError(f"Handshake length must be {HANDSHAKE_LENGTH}")
    if data[:18] != HEADER:
        raise ValueError("Handshake header must match exactly")
    if data[18:28] != ZEROS:
        raise ValueError("Handshake zero bits must be 10 zero bytes")

    # Peer id is the last 4 bytes of the handshake
    return struct.unpack("!I", data[28:32])[0]


# Allow callers to pass either MessageType.INTERESTED or the int 2
def _coerce_message_type(message_type: MessageType | int) -> MessageType:
    if isinstance(message_type, MessageType):
        return message_type
    try:
        return MessageType(int(message_type))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid message type: {message_type!r}") from exc


# make_message = encode or build bytes to send over the socket
# Actual message format
# [4-byte length][1-byte type][payload]
# length does NOT include the 4-byte length field itself
def make_message(message_type: MessageType | int, payload: bytes = b"") -> bytes:
    msg_type = _coerce_message_type(message_type)

    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes or bytearray")

    payload = bytes(payload)
    length = 1 + len(payload)  # 1 byte for type + payload bytes
    return struct.pack("!I", length) + bytes([msg_type.value]) + payload


# parse_message = decode a full message frame we already received
# Input must include the 4-byte length prefix
# Output is a Message object (type + payload) so the rest of the code
# doesnt have to do byte slicing everywhere
def parse_message(frame: bytes) -> Message:
    if len(frame) < 5:
        raise ValueError("Actual message frame must be at least 5 bytes")

    declared_length = struct.unpack("!I", frame[:4])[0]
    actual_body_length = len(frame) - 4
    if declared_length != actual_body_length:
        raise ValueError(
            f"Message length mismatch: declared {declared_length}, actual {actual_body_length}"
        )

    # raw_type is the single type byte directly from the wire (0..7)
    raw_type = frame[4]

    # payload is everything after the type byte and it can be empty
    payload = frame[5:]

    try:
        msg_type = MessageType(raw_type)
    except ValueError as exc:
        raise ValueError(f"Unknown message type byte: {raw_type}") from exc

    return Message(message_type=msg_type, payload=payload)


# TCP recv() can return fewer bytes than requested
# This keeps reading until exactly n bytes are received or the socket closes
def read_exact(sock: socket.socket, n: int) -> bytes:
    if n < 0:
        raise ValueError("n must be non-negative")

    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed while reading")
        data.extend(chunk)
    return bytes(data)


# Read one full handshake frame from a socket and return the peer id
def recv_handshake(sock: socket.socket) -> int:
    data = read_exact(sock, HANDSHAKE_LENGTH)
    return parse_handshake(data)


# Read one full length-prefixed actual message and decode it
def recv_message(sock: socket.socket) -> Message:
    length_prefix = read_exact(sock, 4)
    body_length = struct.unpack("!I", length_prefix)[0]
    body = read_exact(sock, body_length)
    return parse_message(length_prefix + body)


# HAVE and REQUEST payloads are just a 4-byte piece index
def pack_piece_index(piece_index: int) -> bytes:
    if piece_index < 0:
        raise ValueError("piece_index must be non-negative")
    return struct.pack("!I", piece_index)


# Convert a HAVE or REQUEST payload back into a piece index int
def unpack_piece_index(payload: bytes) -> int:
    if len(payload) != 4:
        raise ValueError(f"Piece index payload must be 4 bytes, got {len(payload)}")
    return struct.unpack("!I", payload)[0]


# PIECE payload format
# [4-byte piece index][piece data bytes]
def pack_piece(piece_index: int, piece_data: bytes) -> bytes:
    if not isinstance(piece_data, (bytes, bytearray)):
        raise TypeError("piece_data must be bytes or bytearray")
    return pack_piece_index(piece_index) + bytes(piece_data)


# Split PIECE payload into (piece_index, piece_data)
def unpack_piece(payload: bytes) -> tuple[int, bytes]:
    if len(payload) < 4:
        raise ValueError("PIECE payload must be at least 4 bytes")

    # First 4 bytes = piece index and remaining bytes = actual piece contents
    piece_index = struct.unpack("!I", payload[:4])[0]
    piece_data = payload[4:]
    return piece_index, piece_data
