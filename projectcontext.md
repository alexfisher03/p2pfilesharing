# P2P File Sharing Project (BitTorrent-like)

**Last Updated:** 1/21/2026  
**Language Options:** Java, Python, or C/C++

---

## Due Dates

| Milestone | Deadline |
|---|---|
| Midpoint Check | March 12, 11:59 pm |
| Final Project | April 22, 11:59 pm |

**Late Policy:** No late projects accepted. Start early.

---

## Project Overview

Implement a P2P file sharing system similar to BitTorrent. The key feature to implement is the **choking-unchoking mechanism**. The protocol described below is a slightly modified version of the original BitTorrent protocol.

---

## Group & Submission

- **Group size:** 3–4 persons
- **Midpoint check:** Submit 500+ lines of compilable code (worth 4% of course grade)
- **Submission:** One archive/zip via Canvas containing all source files and files needed to compile/run. Do NOT include executables, object files, `Common.cfg`, `PeerInfo.cfg`, or sample test files.
  ```
  tar cvf proj1.tar foo.java bar.java
  ```
- Only one group member needs to submit. Include all member names in a `readme` file.

---

## Demo

- 5–8 minute recorded video, submitted on Canvas or via OneDrive@UF link.
- Data file exchanged must be **at least 20 MB**; piece size = **16,384 bytes**.
- Must run on **multiple machines**.
- Disk space needed: **150+ MB**.
- Logs are important for scoring.

---

## Protocol Description

All communication uses **TCP**. Interaction between two peers is symmetrical.

### Handshake Message (32 bytes total)

| Field | Size | Value |
|---|---|---|
| Handshake header | 18 bytes | `P2PFILESHARINGPROJ` |
| Zero bits | 10 bytes | `0x00...` |
| Peer ID | 4 bytes | Integer peer ID |

### Actual Messages (post-handshake)

| Field | Size | Description |
|---|---|---|
| Message length | 4 bytes | Length in bytes (excludes itself) |
| Message type | 1 byte | See table below |
| Message payload | Variable | Depends on type |

### Message Types

| Type | Value | Payload |
|---|---|---|
| choke | 0 | None |
| unchoke | 1 | None |
| interested | 2 | None |
| not interested | 3 | None |
| have | 4 | 4-byte piece index |
| bitfield | 5 | Bitfield (1 bit per piece) |
| request | 6 | 4-byte piece index |
| piece | 7 | 4-byte piece index + piece content |

### Bitfield Format

- Sent as the **first message after handshake**
- Each bit represents whether the peer has that piece (1 = has it, 0 = doesn't)
- First byte covers piece indices 0–7 (high bit to low bit); next byte covers 8–15, etc.
- Spare bits at the end are set to 0
- Peers with no pieces may skip the bitfield message

---

## Peer Behavior

### Startup & Handshake

1. Peer A connects to Peer B via TCP
2. Both peers send handshake messages to each other
3. Verify: correct header + expected peer ID
4. Both send `bitfield` messages (unless peer has no pieces)
5. If the other peer has pieces you don't have → send `interested`; otherwise → send `not interested`

### Choking / Unchoking

- Each peer uploads to at most **k preferred neighbors** + **1 optimistically unchoked neighbor**
- **Every p seconds (unchoking interval):** Recalculate preferred neighbors
  - Among **interested** neighbors, pick top-k by download rate (break ties randomly)
  - Send `unchoke` to newly preferred; send `choke` to previously unchoked neighbors no longer preferred (unless optimistically unchoked)
  - If peer has the **complete file**, select preferred neighbors **randomly** among interested neighbors
- **Every m seconds (optimistic unchoking interval):** Pick one random choked+interested neighbor as optimistically unchoked; send `unchoke`
- A peer can be both a preferred neighbor and optimistically unchoked simultaneously

### Interested / Not Interested

- Send `interested` whenever a neighbor has a piece you don't have (triggered by receiving `bitfield` or `have`)
- Send `not interested` if the neighbor has no pieces you need
- Maintain bitfields for all neighbors; update on `have` messages
- After downloading a piece, check all neighbors' bitfields and send `not interested` as needed

### Request / Piece Exchange

- When unchoked by a neighbor → send `request` for a random piece that:
  - The neighbor has
  - You don't have
  - You haven't already requested from another neighbor
- On receiving `request` → send `piece` with actual data
- After receiving a `piece` → send next `request` (sequential, **no pipelining**)
- Continue until choked or no more interesting pieces
- Handle the case where a `piece` response never arrives (peer got choked before responding)
- **No endgame mode; no `cancel` message**

---

## Implementation Specifics

### Configuration Files

#### `Common.cfg`
```
NumberOfPreferredNeighbors 2
UnchokingInterval 5
OptimisticUnchokingInterval 15
FileName TheFile.dat
FileSize 10000232
PieceSize 32768
```
- `UnchokingInterval` and `OptimisticUnchokingInterval` are in **seconds**
- Number of pieces = ceil(FileSize / PieceSize); last piece may be smaller

#### `PeerInfo.cfg`
```
[peer ID] [host name] [listening port] [has file or not]
```
Example:
```
1001 lin114-00.cise.ufl.edu 6008 1
1002 lin114-01.cise.ufl.edu 6008 0
1003 lin114-02.cise.ufl.edu 6008 0
1004 lin114-03.cise.ufl.edu 6008 0
1005 lin114-04.cise.ufl.edu 6008 0
1006 lin114-05.cise.ufl.edu 6008 0
```
- `1` = has complete file; `0` = does not have file
- Multiple peers can have the file
- Acts as the tracker (no separate tracker needed)

### Directory Structure

```
~/project/               ← working directory (executables + config files)
~/project/peer_1001/     ← files for peer 1001
~/project/peer_1002/     ← files for peer 1002
...
```

Peers with the complete file must have it in their subdirectory before starting.

### Peer Process

- Process name: `peerProcess`
- Takes peer ID as argument: `java peerProcess 1001`
- Reads `Common.cfg` and `PeerInfo.cfg` on startup
- Sets bitfield to all-1s if it has the file, all-0s otherwise
- Connects to **all peers listed before it** in `PeerInfo.cfg`
- First peer only listens; does not connect to anyone
- **Terminates when ALL peers (not just itself) have the complete file**

### TCP Connection Strategy

- One TCP connection per pair of peers
- Two threads per socket: one for sending, one for receiving

---

## Logging

Log file location: `~/project/log_peer_[peerID].log`

| Event | Log Format |
|---|---|
| Makes TCP connection | `[Time]: Peer [ID1] makes a connection to Peer [ID2].` |
| Receives TCP connection | `[Time]: Peer [ID1] is connected from Peer [ID2].` |
| Changes preferred neighbors | `[Time]: Peer [ID] has the preferred neighbors [id1,id2,...].` |
| Changes optimistic unchoke | `[Time]: Peer [ID] has the optimistically unchoked neighbor [ID].` |
| Unchoked by neighbor | `[Time]: Peer [ID1] is unchoked by [ID2].` |
| Choked by neighbor | `[Time]: Peer [ID1] is choked by [ID2].` |
| Receives `have` | `[Time]: Peer [ID1] received the 'have' message from [ID2] for the piece [index].` |
| Receives `interested` | `[Time]: Peer [ID1] received the 'interested' message from [ID2].` |
| Receives `not interested` | `[Time]: Peer [ID1] received the 'not interested' message from [ID2].` |
| Downloads a piece | `[Time]: Peer [ID1] has downloaded the piece [index] from [ID2]. Now the number of pieces it has is [n].` |
| Downloads complete file | `[Time]: Peer [ID] has downloaded the complete file.` |

Time format includes: date, hour, minute, second (exact format is up to you).

---

## Hosts for Testing

- **Local dev:** Use `localhost` with multiple peer processes on one machine
- **Multi-machine demo:** Team laptops on same LAN, or use UF VPN (Cisco Secure Client / AnyConnect)
  - VPN info: https://it.ufl.edu/ict/documentation/network-infrastructure/vpn/
- **CISE servers (demo only):** `rain.cise.ufl.edu`, `storm.cise.ufl.edu`, `thunder.cise.ufl.edu`
- **Do not use port 6008** on shared machines — pick your own port to avoid conflicts
- Avoid repeated testing on VPN/CISE servers with unstable implementations

---

## Sample Files (on Canvas under Files/Project)

- `Sample_Client.java`, `Sample_Server.java`
- `project_config_file_small.zip` — ~2 MB data file
- `project_config_file_large.zip` — 20+ MB data file (needed to demo choking/unchoking)

---

## Grading

- Group receives a common grade, then individual adjustments based on effort
- Partial credit available — document what you did and who did what in the `readme`
- Logs are important for scoring

---

## FAQ

**Q: Can I implement on Windows?**  
Yes, but the demo must run on multiple machines.

**Q: Can I assume peer subdirectories are pre-created?**  
Yes.

**Q: How many TCP connections between two peers?**  
One socket per peer pair, with two threads (one send, one receive).

**Q: How is `have` different from `bitfield`?**  
`bitfield` is sent once at startup to convey all pieces. `have` is sent incrementally each time a new single piece is acquired.

**Q: What should I submit for the midpoint check?**  
500+ lines of compilable code.

**Q: How should I start?**  
Read the protocol description carefully. At its core, each peer sends/receives/replies to messages over TCP connections based on the protocol. Once you have the big picture, implementation becomes manageable.

---



---

## References

- Elliotte Rusty Harold. *Java Network Programming*, 4th edition. O'Reilly Media, 2013.
- BitTorrent protocol documentation (searchable online — helpful for understanding the protocol before re-reading the project description)
