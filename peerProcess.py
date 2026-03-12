import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from config import load_common_cfg, load_peer_cfg
from log import PeerLogger
import networking
import protocol


# holds our neighbor states to easily work with
@dataclass
class NeighborState:
    peer_id: int
    bitfield: bytearray  # their pieces
    am_choking: bool = True  # you are choking them
    am_interested: bool = False  # you are interested in them
    peer_choking: bool = True  # they are choking you
    peer_interested: bool = False  # they are interested in you
    bytes_downloaded_from: int = 0  # for rate calculation
    bytes_uploaded_to: int = 0
    download_rate: float = 0.0
    requested_piece: int | None = None  # in-flight request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("peer_id", type=int)
    args = parser.parse_args()

    workdir = Path.cwd()
    common = load_common_cfg(workdir / "Common.cfg")
    peers = load_peer_cfg(workdir / "PeerInfo.cfg")
    logger = PeerLogger(args.peer_id, workdir)

    logger.write(f"Peer {args.peer_id} started.")

    # Find this peer's own entry in the peer list loaded from PeerInfo.cfg
    self_info = None
    for p in peers:
        if p.peer_id == args.peer_id:
            self_info = p
            break

    # If no matching entry was found, the peer_id supplied on the command line is not listed in PeerInfo.cfg
    if self_info is None:
        raise ValueError(
            f"Peer ID {args.peer_id} not found in PeerInfo.cfg. "
            "Check that the peer ID matches an entry in the config file."
        )

    num_pieces = math.ceil(common.file_size / common.piece_size)
    # 8 pieces per byte, round up so the last byte covers any remainder.
    bitfield_len = math.ceil(num_pieces / 8)

    if self_info.has_file:
        own_bitfield = bytearray(bitfield_len)
        # piece i lives in byte (i//8), at bit position (7 - i%8). We OR in a mask to set that bit for each piece.
        # Spare bits in the final byte are never touched and stay 0.
        for i in range(num_pieces):
            own_bitfield[i // 8] |= 1 << (7 - (i % 8))
    else:
        own_bitfield = bytearray(bitfield_len)

    # peer_id -> NeighborState for every peer we will talk to
    neighbors: dict[int, NeighborState] = {}

    # The lambda function that fires when a peer is connected
    def on_connected(remote_id: int, incoming: bool) -> None:
        # By the time this fires, networking.py has already completed the TCP
        # handshake (sent/received the 32-byte P2PFILESHARINGPROJ header).
        # the job here is the application-layer setup

        # Register the neighbor with an all-zero bitfield. We don't know which
        # pieces they have yet, that is filled in when their BITFIELD message arrives in on_message.
        neighbors[remote_id] = NeighborState(
            peer_id=remote_id,
            bitfield=bytearray(bitfield_len),
        )

        # incoming=True means they dialed us, false means we dialed them.
        # The spec requires different log wording for each direction.
        if incoming:
            logger.write(
                f"Peer {self_info.peer_id} is connected from Peer {remote_id}."
            )
        else:
            logger.write(
                f"Peer {self_info.peer_id} makes a connection to Peer {remote_id}."
            )

        # Per the spec, the BITFIELD message is the very first message sent
        # after the handshake so the remote peer learns which pieces we have.
        # Peers with no pieces at all may skip it, so we only send when we
        # actually have something (any non-zero byte in own_bitfield).
        if any(own_bitfield):
            net.send_message(
                remote_id,
                protocol.Message(
                    message_type=protocol.MessageType.BITFIELD,
                    payload=bytes(own_bitfield),
                ),
            )

    # Instantiate the networking class
    net = networking.NetworkManager(
        self_peer_id=self_info.peer_id,
        self_port=self_info.port,
        on_connected=on_connected,
        on_message=lambda remote_id, message: None,
        on_disconnected=lambda remote_id: neighbors.pop(remote_id, None),
    )

    # Start our server from the networking class
    net.start_server()

    # Connect to all peers above US in PeerInfo.cfg
    for p in peers:
        if p.peer_id == self_info.peer_id:
            break
        net.connect_to_peer(p.peer_id, p.host, p.port)


if __name__ == "__main__":
    main()
