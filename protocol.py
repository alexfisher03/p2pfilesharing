import struct
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


# ! == big endian (most significant byte first), I == 4 bytes in length
def make_handshake(peer_id: int) -> bytes:
    return HEADER + ZEROS + struct.pack("!I", peer_id)


def parse_handshake(data: bytes) -> int:
    if len(data) != HANDSHAKE_LENGTH:
        raise ValueError("Handshake length needs to be 32")
    if data[:18] != HEADER:
        raise ValueError("Header must match exactly")
    if data[18:28] != ZEROS:
        raise ValueError("Handshake zero bits must be 10 zero bytes")
    return struct.unpack("!I", data[28:32])[0]  # this is the last four bytes (peerId)


def make_message(messageType: MessageType, payload: bytes = b"") -> bytes:
    if not (0 <= messageType.value <= 7):
        raise ValueError("invalid message type")
    length = 1 + len(payload)  # type byte plus payload
    return struct.pack("!I", length) + bytes([messageType.value]) + payload
