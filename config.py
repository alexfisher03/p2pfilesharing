from dataclasses import dataclass
from pathlib import Path


# matches Common.cfg
@dataclass
class CommonConfig:
    num_pref_neighbors: int
    unchoke_interval: int
    optimistic_interval: int
    file_name: str
    file_size: int
    piece_size: int


# matches PeerInfo.cfg
@dataclass
class PeerInfo:
    peer_id: int
    host: str
    port: int
    has_file: bool


# just loads the config object from the files
def load_common_cfg(path: Path) -> CommonConfig:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue

        key, value = line.split(maxsplit=1)
        values[key] = value
    return CommonConfig(
        num_pref_neighbors=int(values["NumberOfPreferredNeighbors"]),
        unchoke_interval=int(values["UnchokingInterval"]),
        optimistic_interval=int(values["OptimisticUnchokingInterval"]),
        file_name=values["FileName"],
        file_size=int(values["FileSize"]),
        piece_size=int(values["PieceSize"]),
    )


# loads the peers into peer info objects
def load_peer_cfg(path: Path) -> list[PeerInfo]:
    peers = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        peerId, host, port, has_file = line.split()
        peers.append(PeerInfo(int(peerId), host, int(port), has_file == "1"))
    return peers
