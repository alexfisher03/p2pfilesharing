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

    # TODO: find self entry in peers
    # TODO: open server socket on self port
    # TODO: connect to all predecessor peers
    # TODO: exchange handshake then bitfield
    # TODO: message receive loop
    # TODO: choking/unchoking scheduler
    # TODO: request/piece handling
    # TODO: completion detection and shutdown

    _ = common, peers  # silence unused for now


if __name__ == "__main__":
    main()
