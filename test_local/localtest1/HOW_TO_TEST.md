# Local Test Setup

## What's here

- `Common.cfg` — 100 KB file, 16 KB pieces (7 pieces total), 5s unchoke interval
- `PeerInfo.cfg` — 3 peers all on localhost, ports 7001/7002/7003
- `1001/testfile.dat` — the complete 100 KB file (peer 1001 starts with it)
- `1002/` — empty, must download
- `1003/` — empty, must download

## How to run

Open **3 separate terminals**, all from the `test_local/` directory:

```bash
cd /Users/j10/Projects/networks/p2pfilesharing/test_local
```

**Terminal 1** (start first — it has the file):
```bash
python3 ../peerProcess.py 1001
```

**Terminal 2** (start after 1001 is listening):
```bash
python3 ../peerProcess.py 1002
```

**Terminal 3** (start after 1002):
```bash
python3 ../peerProcess.py 1003
```

## What to check

- Logs appear at `test_local/log_peer_1001.log`, `log_peer_1002.log`, `log_peer_1003.log`
- After all peers finish, `peer_1002/testfile.dat` and `peer_1003/testfile.dat` should exist

Verify the downloaded files match the original:
```bash
md5 peer_1001/testfile.dat peer_1002/testfile.dat peer_1003/testfile.dat
```
All three hashes should be identical.

## Cleanup between runs

```bash
rm -f 1002/testfile.dat 1002/piece_* 1003/testfile.dat 1003/piece_* log_peer_*.log
```

## Config notes

| Setting | Value | Why |
|---|---|---|
| FileSize | 102400 (100 KB) | Small enough to transfer fast |
| PieceSize | 16384 (16 KB) | 7 pieces total — enough to see the protocol work |
| UnchokingInterval | 5s | Short so you see neighbor changes quickly |
| OptimisticUnchokingInterval | 15s | Per spec default |
| NumberOfPreferredNeighbors | 2 | Both non-seeder peers can be preferred simultaneously |
| Ports | 7001–7003 | Avoids conflicts with other students using 6008 |
