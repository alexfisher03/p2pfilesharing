# Testing Guide

This document walks through every stage of testing in order, from a quick local smoke test on one machine all the way to the recorded demo on CISE servers. Do not skip phases — each one builds on the last.

---

## Pre-flight Checklist

Before running anything, make sure these are true:

- [ ] Python 3.10+ is installed: `python3 --version`
- [ ] You are running all commands from the project root (the folder containing `peerProcess.py`)
- [ ] No leftover `piece_*` files or old logs in peer directories from a previous run
- [ ] The seed file exists in the seeder's peer directory before any peer starts

---

## Phase 1 — Local Smoke Test (3 peers, 100 KB)

**Goal:** verify TCP connections, handshake, bitfield exchange, piece transfer, and clean shutdown all work. This is the fastest way to confirm nothing is broken before investing time in bigger tests.

**Pre-built setup lives at:** `test_local/localtest1/`

```
localtest1/
  Common.cfg          — 100 KB file, 16 KB pieces (7 pieces), 5s unchoke interval
  PeerInfo.cfg        — 3 peers on localhost:7001/7002/7003
  peer_1001/testfile.dat   — seeder file already in place
  peer_1002/          — empty, will download
  peer_1003/          — empty, will download
```

### Step 1 — Open three terminals, all pointing to localtest1

```bash
cd /path/to/p2pfilesharing/test_local/localtest1
```

Do this in each terminal before continuing.

### Step 2 — Start the seeder first

**Terminal 1:**
```bash
python3 ../../peerProcess.py 1001
```

Wait until you see no errors printed. Peer 1001 is now listening on port 7001.

### Step 3 — Start the leechers

**Terminal 2** (after 1001 is up):
```bash
python3 ../../peerProcess.py 1002
```

**Terminal 3** (after 1002 is up):
```bash
python3 ../../peerProcess.py 1003
```

### Step 4 — Wait for all three to exit

All three processes will terminate automatically once every peer has the complete file. With a 100 KB file and a 5-second unchoke interval, this typically takes 10–30 seconds.

If a peer doesn't exit within a minute, check the logs for errors.

### Step 5 — Verify the transfer was correct

```bash
md5 peer_1001/testfile.dat peer_1002/testfile.dat peer_1003/testfile.dat
```

All three MD5 hashes must be identical. If they differ, the file was corrupted during transfer.

### Step 6 — Check the logs

```bash
cat log_peer_1001.log
cat log_peer_1002.log
cat log_peer_1003.log
```

**Checklist — each log should contain:**

- [ ] `Peer XXXX started.`
- [ ] Connection lines (`makes a connection to` or `is connected from`)
- [ ] `received the 'interested' message from`
- [ ] `has the preferred neighbors [...]` (appears every 5s once transfers begin)
- [ ] `is unchoked by` (leechers only)
- [ ] `has downloaded the piece X from Y. Now the number of pieces it has is N.` (leechers only)
- [ ] `has downloaded the complete file.` (leechers only)

### Step 7 — Clean up before the next run

```bash
rm -f peer_1002/testfile.dat peer_1002/piece_*
rm -f peer_1003/testfile.dat peer_1003/piece_*
rm -f log_peer_*.log
```

---

## Phase 2 — Local Large-File Test (6 peers, 24 MB)

**Goal:** exercise the full choking/unchoking mechanism with a real-sized file. With only 7 pieces in phase 1, choke/unchoke barely has time to do anything. This phase uses the 24 MB `tree.jpg` from the Canvas sample files, which produces enough traffic to see rate-based neighbor selection, optimistic unchokes, and choke/unchoke cycling in the logs.

**This is also your local dry run before going to CISE.** If the transfer breaks here, fix it here — do not start debugging on the CISE servers.

**Pre-built setup lives at:** `test_local/project_config_file_large/`

```
project_config_file_large/
  Common.cfg    — 24 MB file (tree.jpg), PieceSize 16384, 5s unchoke, 10s optimistic
  PeerInfo.cfg  — 6 peers using lin114 CISE hostnames — you MUST edit this for local use
  1001/tree.jpg — seed file already included
  1002/ through 1006/  — empty leecher directories
```

### Step 1 — Adapt PeerInfo.cfg for localhost

The config from Canvas uses `lin114-XX.cise.ufl.edu` hostnames. For local testing, replace those with `localhost` and give each peer a unique port.

Open `test_local/project_config_file_large/PeerInfo.cfg` and replace it with:

```
1001 localhost 7001 1
1002 localhost 7002 0
1003 localhost 7003 0
1004 localhost 7004 0
1005 localhost 7005 0
1006 localhost 7006 0
```

**Do not commit this change** — you will need the original CISE hostnames back for Phase 3. Keep a backup or use `git diff` to restore it.

### Step 2 — Open six terminals, all pointing to the same directory

```bash
cd /path/to/p2pfilesharing/test_local/project_config_file_large
```

### Step 3 — Start all six peers in order

Start them in sequence, waiting a second between each:

```bash
# Terminal 1
python3 ../../peerProcess.py 1001

# Terminal 2
python3 ../../peerProcess.py 1002

# Terminal 3
python3 ../../peerProcess.py 1003

# Terminal 4
python3 ../../peerProcess.py 1004

# Terminal 5
python3 ../../peerProcess.py 1005

# Terminal 6
python3 ../../peerProcess.py 1006
```

### Step 4 — Watch the logs as it runs

In a seventh terminal (same directory), tail a leecher log to see real-time progress:

```bash
tail -f log_peer_1002.log
```

You should see:
- `is unchoked by 1001` early on
- `has downloaded the piece X from Y` lines accumulating
- `has the preferred neighbors` entries changing as rates shift
- `has the optimistically unchoked neighbor` every ~10 seconds
- Eventually `has downloaded the complete file.`

### Step 5 — Verify all six files match

After all processes exit:

```bash
md5 1001/tree.jpg 1002/tree.jpg 1003/tree.jpg 1004/tree.jpg 1005/tree.jpg 1006/tree.jpg
```

All six hashes must be identical.

### Step 6 — Clean up leecher directories

```bash
for i in 1002 1003 1004 1005 1006; do
  rm -f $i/tree.jpg $i/piece_*
done
rm -f log_peer_*.log
```

### Step 7 — Restore PeerInfo.cfg for CISE use

```bash
git checkout test_local/project_config_file_large/PeerInfo.cfg
```

---

## Phase 3 — CISE Server Test (small file, 9 peers)

**Goal:** confirm the code works across real separate machines over the network before the demo. The small file (~2 MB) is faster to transfer and easier to debug if something goes wrong.

**Pre-built setup lives at:** `test_local/project_config_file_small/`

```
project_config_file_small/
  Common.cfg    — ~2 MB file (thefile), PieceSize 16384, 3 preferred neighbors
  PeerInfo.cfg  — 9 peers on lin114-00 through lin114-08, all port 6001
  1001/thefile  — seed file (peer 1001 and 1006 both start with the file)
  1002/ through 1009/  — empty leecher directories
```

Note: peers 1001 AND 1006 are seeders (`has_file = 1`) in this config. This tests the multi-seeder case.

### CISE machine assignments

| Peer | Machine |
|---|---|
| 1001 | lin114-00.cise.ufl.edu |
| 1002 | lin114-01.cise.ufl.edu |
| 1003 | lin114-02.cise.ufl.edu |
| 1004 | lin114-03.cise.ufl.edu |
| 1005 | lin114-04.cise.ufl.edu |
| 1006 | lin114-05.cise.ufl.edu |
| 1007 | lin114-06.cise.ufl.edu |
| 1008 | lin114-07.cise.ufl.edu |
| 1009 | lin114-08.cise.ufl.edu |

You can use three team member laptops running `ssh` to drive multiple machines at once, or just pick three of the peers to run (e.g., 1001, 1002, 1003) to keep it manageable.

### Step 1 — SSH into each machine and set up the project directory

From your laptop:

```bash
ssh your_gatorlink@lin114-00.cise.ufl.edu
```

On each machine, create the project directory and copy the files:

```bash
mkdir -p ~/p2pproject
cd ~/p2pproject
```

Copy the source files and the config bundle. From your local machine (run this for each CISE host):

```bash
scp peerProcess.py networking.py protocol.py config.py log.py \
    your_gatorlink@lin114-00.cise.ufl.edu:~/p2pproject/

scp -r test_local/project_config_file_small/Common.cfg \
        test_local/project_config_file_small/PeerInfo.cfg \
        test_local/project_config_file_small/1001 \
        test_local/project_config_file_small/1002 \
        your_gatorlink@lin114-00.cise.ufl.edu:~/p2pproject/
```

Adjust which peer directories you copy to each machine. Machine lin114-00 needs `1001/`, machine lin114-01 needs `1002/`, and so on.

For the seeders (machines 00 and 05), make sure `thefile` is inside the peer directory:

```bash
ls ~/p2pproject/1001/   # should show: thefile
ls ~/p2pproject/1006/   # should show: thefile
```

### Step 2 — Use tmux or screen so SSH disconnects don't kill the process

On each CISE machine:

```bash
tmux new -s p2p
cd ~/p2pproject
```

If you get disconnected, reconnect with `tmux attach -t p2p`.

### Step 3 — Start peers in PeerInfo.cfg order

Start lin114-00 (peer 1001) first, then 01 (1002), and so on. You do not need to start all 9 — you can test with just 3 or 4 to confirm cross-machine transfer works.

**lin114-00 (peer 1001):**
```bash
cd ~/p2pproject && python3 peerProcess.py 1001
```

**lin114-01 (peer 1002):**
```bash
cd ~/p2pproject && python3 peerProcess.py 1002
```

**lin114-05 (peer 1006, second seeder):**
```bash
cd ~/p2pproject && python3 peerProcess.py 1006
```

Wait for all running peers to exit naturally.

### Step 4 — Verify transferred files

On each leecher machine:

```bash
md5sum ~/p2pproject/1002/thefile
```

Compare against the seeder's hash:

```bash
# on lin114-00
md5sum ~/p2pproject/1001/thefile
```

All must match.

### Step 5 — Check logs for required events

Pull logs back to your local machine for review:

```bash
scp your_gatorlink@lin114-00.cise.ufl.edu:~/p2pproject/log_peer_1001.log ./cise_log_1001.log
scp your_gatorlink@lin114-01.cise.ufl.edu:~/p2pproject/log_peer_1002.log ./cise_log_1002.log
```

Check that all 11 required log event types are present across the logs (see Phase 1 checklist above).

---

## Phase 4 — CISE Server Test (large file, 6 peers) — Demo-Ready

**Goal:** final test with the actual demo file. This is what you record. The file is 24 MB (`tree.jpg`), which is large enough for the choking/unchoking mechanism to be clearly observable in the logs over the course of the transfer.

**Pre-built setup lives at:** `test_local/project_config_file_large/`

```
project_config_file_large/
  Common.cfg    — tree.jpg, 24301474 bytes, PieceSize 16384 (1483 pieces), 5s unchoke
  PeerInfo.cfg  — 6 peers on lin114-00 through lin114-05, port 6001
  1001/tree.jpg — seed file
  1002/ through 1006/ — empty
```

### CISE machine assignments

| Peer | Machine |
|---|---|
| 1001 | lin114-00.cise.ufl.edu |
| 1002 | lin114-01.cise.ufl.edu |
| 1003 | lin114-02.cise.ufl.edu |
| 1004 | lin114-03.cise.ufl.edu |
| 1005 | lin114-04.cise.ufl.edu |
| 1006 | lin114-05.cise.ufl.edu |

### Step 1 — Copy files to each CISE machine

Repeat the `scp` steps from Phase 3 but using the `project_config_file_large` directory. Each machine gets:
- All five `.py` source files
- `Common.cfg` and `PeerInfo.cfg`
- Its own peer directory (lin114-00 gets `1001/tree.jpg`, everyone else gets their empty directory)

Verify the seed file on lin114-00:

```bash
ls -lh ~/p2pproject/1001/tree.jpg   # should show ~23 MB
```

### Step 2 — Clean all machines before starting

On each machine, make sure there are no leftover files from phase 3:

```bash
rm -f ~/p2pproject/1002/tree.jpg ~/p2pproject/1002/piece_* ~/p2pproject/log_peer_1002.log
# repeat for each leecher peer directory
```

### Step 3 — Start recording

Start your screen recorder before launching any peers. The demo video must be 5–8 minutes and show:
- All peers starting up
- Logs showing connection events, interested messages, unchoke events, piece downloads
- Choke/unchoke cycling (preferred neighbors changing over time)
- Optimistic unchoke rotations
- All peers finishing with "downloaded the complete file"

### Step 4 — Start peers in order

Coordinate with teammates. Each person SSHes into their assigned machine and runs their peer. Start in peer ID order — lin114-00 first, then lin114-01, etc.

```bash
# lin114-00
cd ~/p2pproject && python3 peerProcess.py 1001

# lin114-01 (after 1001 is up)
cd ~/p2pproject && python3 peerProcess.py 1002

# continue through 1006
```

With 6 peers and a 24 MB file, the full transfer typically completes in 1–3 minutes depending on network conditions. All six processes will exit automatically.

### Step 5 — Tail logs while recording for visual proof

While the transfer runs, in a separate SSH session show the live log:

```bash
tail -f ~/p2pproject/log_peer_1002.log
```

This shows the piece download count rising in real time, which makes for compelling demo footage.

### Step 6 — Verify all files match after completion

On each machine:

```bash
md5sum ~/p2pproject/100X/tree.jpg
```

All six hashes must be identical. Do this on camera if possible.

### Step 7 — Collect all logs for submission

Pull all six logs back to your local machine:

```bash
for i in 00 01 02 03 04 05; do
  scp your_gatorlink@lin114-$i.cise.ufl.edu:~/p2pproject/log_peer_100*.log ./
done
```

Keep these — they are part of the grading criteria.

---

## Phase 5 — Demo Recording Checklist

The spec requires a 5–8 minute recorded video submitted on Canvas or OneDrive@UF.

Before you hit record, make sure you can show:

- [ ] **Multiple machines** — at least 3 separate SSH sessions visible, each on a different CISE host
- [ ] **Startup in order** — show each peer process starting, show it connect and log the connection event
- [ ] **Interest exchange** — log lines showing `received the 'interested' message` after the seeder sends its bitfield
- [ ] **Unchoke events** — leecher logs showing `is unchoked by 1001` triggering piece requests
- [ ] **Piece downloads accumulating** — the piece count going up, e.g. `Now the number of pieces it has is 47`
- [ ] **Choking/unchoking cycling** — `has the preferred neighbors` lines changing between unchoke intervals
- [ ] **Optimistic unchoke** — `has the optimistically unchoked neighbor` lines appearing on the seeder
- [ ] **Completion** — every peer logs `has downloaded the complete file.`
- [ ] **File verification** — run `md5sum` on all machines on camera and confirm matching hashes
- [ ] **File is 20+ MB** — tree.jpg is 24,301,474 bytes, which satisfies this requirement
- [ ] **PieceSize is 16,384** — already set in Common.cfg

**Tip:** use `tmux` with split panes to show multiple peer logs simultaneously on one screen during recording. It makes it easier for the viewer to follow what is happening across machines in real time.

---

## Troubleshooting

**A leecher process prints "failed to connect to peer XXXX after 5 attempts"**
The target machine's peer process wasn't started yet, or the hostname/port in `PeerInfo.cfg` is wrong. Start in order and double-check the config. This peer will have no connection to that neighbor for the session.

**Processes are running but no piece downloads appear in logs**
The choking/unchoking interval hasn't fired yet — wait at least `UnchokingInterval` seconds (5s in the configs). If nothing appears after 20–30 seconds, the seeder may not have received an `interested` message from anyone. Check the seeder's log for connection events.

**Files differ after transfer (md5 mismatch)**
Make sure `FileSize` in `Common.cfg` exactly matches the real file size. Check with:
```bash
wc -c 1001/tree.jpg
```
If this doesn't match the `FileSize` field, update the config.

**Process hangs and never exits**
A peer might be waiting for a neighbor that already disconnected. If you are not running all 6 (or 9) peers, the remaining process may not be able to confirm everyone is done. For partial-peer test runs, use `Ctrl+C` to exit manually.

**Port already in use on CISE**
Someone else is using port 6001 on that machine. Pick a different port (e.g., 7001) and update both `PeerInfo.cfg` on all machines.

**On CISE specifically — do not use port 6008.** This is the default listed in the spec example and other students may be using it. The provided configs already use port 6001 to avoid this.
