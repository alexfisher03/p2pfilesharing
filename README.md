# P2P File Sharing — BitTorrent-style

A simplified BitTorrent-style P2P file sharing system written in Python. Multiple peer processes exchange pieces of a file over TCP until every peer in the network has a complete copy. Implements the full choking/unchoking mechanism, bitfield tracking, and proper shutdown when all peers finish.

**Group members:** Jason, Nick, Alex

---

## How It Works (high level)

- One or more peers start with the complete file (seeders). The rest start with nothing (leechers).
- Every peer connects via TCP to all peers listed before it in `PeerInfo.cfg`.
- After connecting, peers exchange bitfields, send interested/not-interested, and start trading pieces.
- Every `UnchokingInterval` seconds each peer re-ranks its neighbors by download rate and unchokes the top-k. Every `OptimisticUnchokingInterval` seconds one random choked-but-interested neighbor gets a free unchoke slot.
- Piece selection is random — no rarest-first, no pipelining.
- Each peer terminates automatically once it confirms every connected neighbor has the complete file.

---

## File Structure

```
p2pfilesharing/
  peerProcess.py   -- main entry point, all protocol logic and state
  networking.py    -- TCP layer (server, accept loop, send/recv threads)
  protocol.py      -- wire format (handshake, messages, pack/unpack helpers)
  config.py        -- loads Common.cfg and PeerInfo.cfg into dataclasses
  log.py           -- timestamped log writer

  Common.cfg       -- shared settings (piece size, intervals, file name)
  PeerInfo.cfg     -- peer list (id, host, port, has_file)

  peer_1001/       -- working directory for peer 1001 (file lives here if seeder)
  peer_1002/       -- working directory for peer 1002
  ...

  log_peer_1001.log  -- written at runtime, one per peer
  log_peer_1002.log
  ...
```

---

## Requirements

- Python 3.10 or newer (uses `int | None` type union syntax)
- No third-party packages — standard library only

---

## Configuration Files

### `Common.cfg`

```
NumberOfPreferredNeighbors 2
UnchokingInterval 5
OptimisticUnchokingInterval 15
FileName testfile.dat
FileSize 102400
PieceSize 16384
```

| Field | Description |
|---|---|
| `NumberOfPreferredNeighbors` | How many peers each node unchokes per interval |
| `UnchokingInterval` | Seconds between preferred neighbor recalculations |
| `OptimisticUnchokingInterval` | Seconds between optimistic unchoke rotations |
| `FileName` | Name of the file being shared |
| `FileSize` | Total file size in bytes |
| `PieceSize` | Size of each piece in bytes (last piece may be smaller) |

### `PeerInfo.cfg`

```
1001 localhost 7001 1
1002 localhost 7002 0
1003 localhost 7003 0
```

One peer per line: `[peer_id] [host] [port] [has_file]`

- `has_file = 1` means this peer starts with the complete file (seeder)
- `has_file = 0` means this peer starts empty (leecher)
- Order matters — each peer connects to all peers listed above it

---

## Running Locally (Single Machine, Multiple Terminals)

This is the standard way to test. All peers run on `localhost` with different ports.

### Step 1 — Set up the working directory

Pick a directory to run everything from. All peers read config from the current directory and write logs there too.

```
mkdir test_run
cd test_run
```

### Step 2 — Create the config files

Create `Common.cfg`:
```
NumberOfPreferredNeighbors 2
UnchokingInterval 5
OptimisticUnchokingInterval 15
FileName testfile.dat
FileSize 102400
PieceSize 16384
```

Create `PeerInfo.cfg`:
```
1001 localhost 7001 1
1002 localhost 7002 0
1003 localhost 7003 0
```

### Step 3 — Create peer subdirectories and seed file

```bash
mkdir peer_1001 peer_1002 peer_1003
```

The seeder needs the actual file before starting:
```bash
# create a 100KB test file (matches FileSize = 102400 above)
dd if=/dev/urandom of=peer_1001/testfile.dat bs=1024 count=100
```

For the demo (20MB+ file required), adjust `FileSize` and generate accordingly:
```bash
dd if=/dev/urandom of=peer_1001/testfile.dat bs=1M count=20
# then update Common.cfg: FileSize 20971520
```

### Step 4 — Start peers in order

Open a separate terminal for each peer. **Always start peer 1001 first**, then 1002, then 1003. Each later peer tries to connect to earlier ones on startup.

**Terminal 1:**
```bash
cd test_run
python3 /path/to/peerProcess.py 1001
```

**Terminal 2:**
```bash
cd test_run
python3 /path/to/peerProcess.py 1002
```

**Terminal 3:**
```bash
cd test_run
python3 /path/to/peerProcess.py 1003
```

Each process will print errors to stdout and write events to its log file. They shut down automatically when all peers have the complete file.

### Step 5 — Verify the output

After all processes exit, check:

```bash
# logs should show the full exchange
cat log_peer_1001.log
cat log_peer_1002.log
cat log_peer_1003.log

# leechers should have the assembled file
diff peer_1001/testfile.dat peer_1002/testfile.dat
diff peer_1001/testfile.dat peer_1003/testfile.dat

# no diff output = files are identical, transfer was correct
```

---

## What the Logs Should Look Like

A successful 3-peer run produces logs roughly like this:

**log_peer_1001.log** (seeder)
```
[2026-04-22 13:49:02]: Peer 1001 started.
[2026-04-22 13:49:13]: Peer 1001 is connected from Peer 1002.
[2026-04-22 13:49:13]: Peer 1001 received the 'interested' message from 1002.
[2026-04-22 13:49:17]: Peer 1001 is connected from Peer 1003.
[2026-04-22 13:49:17]: Peer 1001 received the 'interested' message from 1003.
[2026-04-22 13:49:18]: Peer 1001 has the preferred neighbors [1002,1003].
[2026-04-22 13:49:32]: Peer 1001 has the optimistically unchoked neighbor 1002.
```

**log_peer_1002.log** (leecher)
```
[2026-04-22 13:49:13]: Peer 1002 started.
[2026-04-22 13:49:13]: Peer 1002 makes a connection to Peer 1001.
[2026-04-22 13:49:17]: Peer 1002 is connected from Peer 1003.
[2026-04-22 13:49:18]: Peer 1002 is unchoked by 1001.
[2026-04-22 13:49:18]: Peer 1002 has downloaded the piece 3 from 1001. Now the number of pieces it has is 1.
[2026-04-22 13:49:18]: Peer 1002 received the 'have' message from 1003 for the piece 5.
...
[2026-04-22 13:49:45]: Peer 1002 has downloaded the complete file.
```

### All required log events

| Event | Example |
|---|---|
| TCP connection made | `Peer 1002 makes a connection to Peer 1001.` |
| TCP connection received | `Peer 1001 is connected from Peer 1002.` |
| Preferred neighbors updated | `Peer 1001 has the preferred neighbors [1002,1003].` |
| Optimistic unchoke | `Peer 1001 has the optimistically unchoked neighbor 1002.` |
| Unchoked by neighbor | `Peer 1002 is unchoked by 1001.` |
| Choked by neighbor | `Peer 1002 is choked by 1001.` |
| Have message received | `Peer 1002 received the 'have' message from 1003 for the piece 5.` |
| Interested received | `Peer 1001 received the 'interested' message from 1002.` |
| Not interested received | `Peer 1001 received the 'not interested' message from 1002.` |
| Piece downloaded | `Peer 1002 has downloaded the piece 3 from 1001. Now the number of pieces it has is 1.` |
| File complete | `Peer 1002 has downloaded the complete file.` |

---

## Testing Across Multiple Machines (Demo Setup)

The demo requires at least 3 machines. Options:
- Three laptops on the same LAN (WiFi or ethernet)
- UF VPN + three CISE servers (`rain`, `storm`, `thunder`)

### Step 1 — Find each machine's IP or hostname

On each machine:
```bash
hostname -I   # Linux
ipconfig getifaddr en0   # macOS
```

Or use hostnames if they resolve on the LAN.

### Step 2 — Update PeerInfo.cfg with real addresses

```
1001 192.168.1.10 7001 1
1002 192.168.1.11 7001 0
1003 192.168.1.12 7001 0
```

All three machines can use the same port since they're on different hosts.

### Step 3 — Copy files to each machine

Each machine needs:
- `peerProcess.py`, `networking.py`, `protocol.py`, `config.py`, `log.py`
- `Common.cfg` and `PeerInfo.cfg` (identical copies on all machines)
- The seeder machine needs `peer_1001/testfile.dat`
- Leecher machines need the empty `peer_1002/` or `peer_1003/` directory

```bash
# example using scp to copy everything to machine 2
scp -r . user@192.168.1.11:~/p2ptest/
```

### Step 4 — Start in order, one machine at a time

Machine 1 (seeder, peer 1001):
```bash
cd ~/p2ptest
python3 peerProcess.py 1001
```

Machine 2 (peer 1002) — after machine 1 is listening:
```bash
cd ~/p2ptest
python3 peerProcess.py 1002
```

Machine 3 (peer 1003):
```bash
cd ~/p2ptest
python3 peerProcess.py 1003
```

### Step 5 — Verify

After all processes exit, run `diff` on the files across machines (e.g., via `scp` to pull them to one place):
```bash
scp user@192.168.1.11:~/p2ptest/peer_1002/testfile.dat ./peer_1002_remote.dat
diff peer_1001/testfile.dat peer_1002_remote.dat
```

---

## Using the test_local/ Directory

There's a pre-configured `test_local/` folder you can use as the working directory for quick local runs. It already has `Common.cfg`, `PeerInfo.cfg`, and the seeder file at `peer_1001/testfile.dat`.

```bash
cd test_local
python3 ../peerProcess.py 1001   # terminal 1
python3 ../peerProcess.py 1002   # terminal 2
python3 ../peerProcess.py 1003   # terminal 3
```

To reset between test runs:
```bash
# remove downloaded pieces and assembled files from leechers
rm -f peer_1002/piece_* peer_1002/testfile.dat
rm -f peer_1003/piece_* peer_1003/testfile.dat
# remove old logs
rm -f log_peer_100*.log
```

---

## Troubleshooting

**Peer fails to connect with "Connection refused"**
- You started a later peer before an earlier one was listening. Start in `PeerInfo.cfg` order. The retry logic will attempt 5 times with 1-second gaps, but if all attempts fail, the peer won't have that connection.

**Processes hang and never exit**
- Check that `UnchokingInterval` in `Common.cfg` is actually firing — logs should show preferred neighbor lines. If no choke/unchoke events appear, the process started fine but transfers haven't begun.
- Make sure the seeder has the file at `peer_[id]/[FileName]` before starting.
- Verify `FileSize` in `Common.cfg` matches the actual byte size of the file: `wc -c peer_1001/testfile.dat`

**Files differ after transfer**
- Check `FileSize` in `Common.cfg` matches exactly. An off-by-one causes the last piece to be wrong size.
- Make sure you're not running two test sessions simultaneously with leftover `piece_*` files from a previous run. Clean between runs.

**Port already in use**
- Another process is on that port. Change the port in `PeerInfo.cfg`, or kill the old process: `lsof -i :7001`

**On shared CISE machines**
- Do not use port 6008 — it's the default and other students likely have something there. Use ports in the 7000–8000 range and avoid common ones.

---

## Protocol Reference (quick summary)

**Handshake** — 32 bytes: `"P2PFILESHARINGPROJ"` (18B) + 10 zero bytes + peer ID (4B, big-endian)

**All other messages** — `[4B length][1B type][payload]` where length = bytes of type + payload

| Type | Value | Payload |
|---|---|---|
| choke | 0 | none |
| unchoke | 1 | none |
| interested | 2 | none |
| not interested | 3 | none |
| have | 4 | 4-byte piece index |
| bitfield | 5 | bitfield bytes |
| request | 6 | 4-byte piece index |
| piece | 7 | 4-byte piece index + data |
