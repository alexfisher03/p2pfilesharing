import argparse
from pathlib import Path

from config import load_common_cfg, load_peer_cfg
from log import PeerLogger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("peer_id", type=int)
    args = parser.parse_args()

    workdir = Path.cwd()
    common = load_common_cfg(workdir / "Common.cfg")
    peers = load_peer_cfg(workdir / "PeerInfo.cfg")
    logger = PeerLogger(args.peer_id, workdir)

    logger.write(f"Peer {args.peer_id} started.")

    # Find this peer's own entry in the peer list loaded from PeerInfo.cfg.
    # Each entry in `peers` is a PeerInfo dataclass with peer_id, host, port,
    # and has_file. We search by matching peer_id to the one passed on the
    # command line so we know our own host/port and whether we start with the file.
    self_info = None
    for p in peers:
        if p.peer_id == args.peer_id:
            self_info = p
            break

    # If no matching entry was found, the peer_id supplied on the command line
    # is not listed in PeerInfo.cfg — this is a configuration error and we
    # cannot continue safely, so raise a clear exception immediately.
    if self_info is None:
        raise ValueError(
            f"Peer ID {args.peer_id} not found in PeerInfo.cfg. "
            "Check that the peer ID matches an entry in the config file."
        )

    _ = common  # silence unused for now


if __name__ == "__main__":
    main()
