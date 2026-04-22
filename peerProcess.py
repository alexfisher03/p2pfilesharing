import argparse
import math
import random
import threading
import time
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


class PeerSession:
    def __init__(self, workdir: Path, common, peers, self_info, logger):
        self.workdir = workdir
        self.common = common
        self.peers = peers
        self.self_info = self_info
        self.logger = logger

        self.num_pieces = math.ceil(common.file_size / common.piece_size)
        # 8 pieces per byte, round up so the last byte covers any remainder.
        self.bitfield_len = math.ceil(self.num_pieces / 8)

        if self_info.has_file:
            self.own_bitfield = bytearray(self.bitfield_len)
            # piece i lives in byte (i//8), at bit position (7 - i%8).
            for i in range(self.num_pieces):
                self.own_bitfield[i // 8] |= 1 << (7 - (i % 8))
        else:
            self.own_bitfield = bytearray(self.bitfield_len)

        # peer_id -> NeighborState for every peer we will talk to
        self.neighbors: dict[int, NeighborState] = {}

        # Piece indices currently requested across all neighbors — avoids requesting
        # the same piece from two peers at once (spec: "has not requested from other neighbors")
        self.in_flight_requests: set[int] = set()

        # one thread runs per peer connection so own_bitfield and in_flight_requests
        # can get hit from multiple threads at the same time -- this lock makes sure
        # only one thread touches them at a time so we dont end up with corrupted state
        self._state_lock = threading.Lock()

        self.net: networking.NetworkManager | None = None

    # ----- file helpers -----

    def peer_dir(self) -> Path:
        # Each peer keeps its files in peer_<id>/ under the working directory
        d = self.workdir / f"peer_{self.self_info.peer_id}"
        d.mkdir(exist_ok=True)
        return d

    def read_piece(self, piece_index: int) -> bytes | None:
        # If the complete file is already present (initial seeder or fully assembled),
        # read the right byte range directly from it.
        full_path = self.peer_dir() / self.common.file_name
        if full_path.exists():
            offset = piece_index * self.common.piece_size
            size = min(self.common.piece_size, self.common.file_size - offset)
            with full_path.open("rb") as f:
                f.seek(offset)
                return f.read(size)
        # Otherwise look for an individual piece file written during download
        piece_path = self.peer_dir() / f"piece_{piece_index}"
        if piece_path.exists():
            return piece_path.read_bytes()
        return None

    def write_piece(self, piece_index: int, data: bytes) -> None:
        (self.peer_dir() / f"piece_{piece_index}").write_bytes(data)

    def assemble_file(self) -> None:
        # Concatenate every piece file into the final file in order
        out_path = self.peer_dir() / self.common.file_name
        with out_path.open("wb") as f:
            for i in range(self.num_pieces):
                data = self.read_piece(i)
                if data:
                    f.write(data)

    # ----- bitfield helpers -----

    def has_piece(self, idx: int) -> bool:
        return bool(self.own_bitfield[idx // 8] & (1 << (7 - (idx % 8))))

    def neighbor_has_piece(self, nbr: NeighborState, idx: int) -> bool:
        if idx // 8 >= len(nbr.bitfield):
            return False
        return bool(nbr.bitfield[idx // 8] & (1 << (7 - (idx % 8))))

    def count_pieces(self) -> int:
        return sum(1 for i in range(self.num_pieces) if self.has_piece(i))

    # ----- interest helpers -----

    def has_interesting_pieces(self, nbr: NeighborState) -> bool:
        # True if the neighbor has at least one piece we still need
        return any(
            self.neighbor_has_piece(nbr, i) and not self.has_piece(i)
            for i in range(self.num_pieces)
        )

    def update_interest(self, remote_id: int, nbr: NeighborState) -> None:
        # Send INTERESTED / NOT_INTERESTED only when our interest state actually changes
        interested = self.has_interesting_pieces(nbr)
        if interested and not nbr.am_interested:
            nbr.am_interested = True
            self.net.send_message(
                remote_id, protocol.Message(protocol.MessageType.INTERESTED)
            )
        elif not interested and nbr.am_interested:
            nbr.am_interested = False
            self.net.send_message(
                remote_id, protocol.Message(protocol.MessageType.NOT_INTERESTED)
            )

    # ----- request helper -----

    def maybe_request(self, remote_id: int, nbr: NeighborState) -> None:
        # Pick a random piece the neighbor has that we need and haven't requested yet
        # hold the lock for the whole check + add so two threads cant pick the same piece
        with self._state_lock:
            candidates = [
                i
                for i in range(self.num_pieces)
                if not self.has_piece(i)
                and self.neighbor_has_piece(nbr, i)
                and i not in self.in_flight_requests
            ]
            if not candidates:
                return
            piece_index = random.choice(candidates)
            nbr.requested_piece = piece_index
            self.in_flight_requests.add(piece_index)
        self.net.send_message(
            remote_id,
            protocol.Message(
                message_type=protocol.MessageType.REQUEST,
                payload=protocol.pack_piece_index(piece_index),
            ),
        )

    # ----- rate tracking -----

    def _snapshot_rates(self) -> None:
        # called every unchoke_interval seconds -- capture how many bytes we downloaded
        # from each neighbor during that window, convert to bytes/sec, then reset the
        # counter so the next interval starts fresh
        interval = self.common.unchoke_interval
        with self._state_lock:
            for nbr in self.neighbors.values():
                nbr.download_rate = nbr.bytes_downloaded_from / interval
                nbr.bytes_downloaded_from = 0

    def _rate_snapshot_loop(self) -> None:
        while not self.net._shutdown.is_set():
            time.sleep(self.common.unchoke_interval)
            self._snapshot_rates()

    # ----- message / connection callbacks -----

    def on_message(self, remote_id: int, message: protocol.Message) -> None:
        nbr = self.neighbors.get(remote_id)
        if nbr is None:
            return

        mtype = message.message_type

        if mtype == protocol.MessageType.CHOKE:
            # They are now choking us, cancel our in-flight request since no piece is coming
            nbr.peer_choking = True
            with self._state_lock:
                if nbr.requested_piece is not None:
                    self.in_flight_requests.discard(nbr.requested_piece)
                    nbr.requested_piece = None
            self.logger.write(
                f"Peer {self.self_info.peer_id} is choked by {remote_id}."
            )

        elif mtype == protocol.MessageType.UNCHOKE:
            # They are unchoking us — we can now send a request
            nbr.peer_choking = False
            self.logger.write(
                f"Peer {self.self_info.peer_id} is unchoked by {remote_id}."
            )
            self.maybe_request(remote_id, nbr)

        elif mtype == protocol.MessageType.INTERESTED:
            # They want pieces from us
            nbr.peer_interested = True
            self.logger.write(
                f"Peer {self.self_info.peer_id} received the 'interested' message from {remote_id}."
            )

        elif mtype == protocol.MessageType.NOT_INTERESTED:
            # They no longer want anything from us
            nbr.peer_interested = False
            self.logger.write(
                f"Peer {self.self_info.peer_id} received the 'not interested' message from {remote_id}."
            )

        elif mtype == protocol.MessageType.HAVE:
            # They finished downloading a new piece — update their bitfield
            piece_index = protocol.unpack_piece_index(message.payload)
            nbr.bitfield[piece_index // 8] |= 1 << (7 - (piece_index % 8))
            self.logger.write(
                f"Peer {self.self_info.peer_id} received the 'have' message from {remote_id} "
                f"for the piece {piece_index}."
            )
            # They may now have something we want
            self.update_interest(remote_id, nbr)

        elif mtype == protocol.MessageType.BITFIELD:
            # First message after handshake — replace their all-zero placeholder with reality
            length = min(len(message.payload), len(nbr.bitfield))
            nbr.bitfield[:length] = message.payload[:length]
            # Decide if we're interested based on what they have
            self.update_interest(remote_id, nbr)

        elif mtype == protocol.MessageType.REQUEST:
            # They want a piece from us — only serve it if we are currently unchoking them
            piece_index = protocol.unpack_piece_index(message.payload)
            if not nbr.am_choking:
                piece_data = self.read_piece(piece_index)
                if piece_data is not None:
                    self.net.send_message(
                        remote_id,
                        protocol.Message(
                            message_type=protocol.MessageType.PIECE,
                            payload=protocol.pack_piece(piece_index, piece_data),
                        ),
                    )
                    nbr.bytes_uploaded_to += len(piece_data)

        elif mtype == protocol.MessageType.PIECE:
            piece_index, piece_data = protocol.unpack_piece(message.payload)

            # write to disk first before we tell anyone we have it
            self.write_piece(piece_index, piece_data)

            # now lock to update the two shared structures together atomically
            with self._state_lock:
                self.in_flight_requests.discard(piece_index)
                nbr.requested_piece = None
                nbr.bytes_downloaded_from += len(piece_data)
                self.own_bitfield[piece_index // 8] |= 1 << (7 - (piece_index % 8))
                piece_count = self.count_pieces()
            self.logger.write(
                f"Peer {self.self_info.peer_id} has downloaded the piece {piece_index} from {remote_id}. "
                f"Now the number of pieces it has is {piece_count}."
            )

            # Announce the new piece to every connected peer so they can update their interest
            self.net.broadcast_message(
                protocol.Message(
                    message_type=protocol.MessageType.HAVE,
                    payload=protocol.pack_piece_index(piece_index),
                )
            )

            # Check if this was the last piece we needed
            if piece_count == self.num_pieces:
                self.assemble_file()
                self.logger.write(
                    f"Peer {self.self_info.peer_id} has downloaded the complete file."
                )

            # Re-evaluate interest in all neighbors now that our bitfield changed
            for nid, n in list(self.neighbors.items()):
                self.update_interest(nid, n)

            # Keep the pipeline going — ask for the next piece if still unchoked
            if not nbr.peer_choking:
                self.maybe_request(remote_id, nbr)

    def on_connected(self, remote_id: int, incoming: bool) -> None:
        # By the time this fires, networking.py has already completed the TCP
        # handshake (sent/received the 32-byte P2PFILESHARINGPROJ header).
        # The job here is the application-layer setup.

        # Register the neighbor with an all-zero bitfield. We don't know which
        # pieces they have yet; that is filled in when their BITFIELD message arrives.
        self.neighbors[remote_id] = NeighborState(
            peer_id=remote_id,
            bitfield=bytearray(self.bitfield_len),
        )

        # incoming=True means they dialed us, False means we dialed them.
        if incoming:
            self.logger.write(
                f"Peer {self.self_info.peer_id} is connected from Peer {remote_id}."
            )
        else:
            self.logger.write(
                f"Peer {self.self_info.peer_id} makes a connection to Peer {remote_id}."
            )

        # Per the spec, the BITFIELD message is the very first message sent after the handshake.
        # Peers with no pieces at all may skip it, so we only send when we have something.
        if any(self.own_bitfield):
            self.net.send_message(
                remote_id,
                protocol.Message(
                    message_type=protocol.MessageType.BITFIELD,
                    payload=bytes(self.own_bitfield),
                ),
            )

    # ----- main loop -----

    def run(self) -> None:
        self.net = networking.NetworkManager(
            self_peer_id=self.self_info.peer_id,
            self_port=self.self_info.port,
            on_connected=self.on_connected,
            on_message=self.on_message,
            on_disconnected=lambda remote_id: self.neighbors.pop(remote_id, None),
        )

        self.net.start_server()

        threading.Thread(target=self._rate_snapshot_loop, daemon=True).start()

        # Connect to all peers listed above us in PeerInfo.cfg
        for p in self.peers:
            if p.peer_id == self.self_info.peer_id:
                break
            self.net.connect_to_peer(p.peer_id, p.host, p.port)

        # Keep the main thread alive so daemon threads stay running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.net.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("peer_id", type=int)
    args = parser.parse_args()

    workdir = Path.cwd()
    common = load_common_cfg(workdir / "Common.cfg")
    peers = load_peer_cfg(workdir / "PeerInfo.cfg")
    logger = PeerLogger(args.peer_id, workdir)

    logger.write(f"Peer {args.peer_id} started.")

    self_info = next((p for p in peers if p.peer_id == args.peer_id), None)
    if self_info is None:
        raise ValueError(
            f"Peer ID {args.peer_id} not found in PeerInfo.cfg. "
            "Check that the peer ID matches an entry in the config file."
        )

    PeerSession(workdir, common, peers, self_info, logger).run()


if __name__ == "__main__":
    main()
