from datetime import datetime
from pathlib import Path


class PeerLogger:
    def __init__(self, peer_id: int, workdir: Path):
        self.peer_id = peer_id
        self.path = workdir / f"log_peer_{peer_id}.log"

    def write(self, text: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a") as f:
            f.write(f"[{ts}]: {text}\n")
