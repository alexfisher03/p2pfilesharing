# Goal

The objective is to build a **Peer-to-Peer (P2P) file-sharing software** similar to BitTorrent. You will implement a protocol that allows multiple peer processes to exchange pieces of a file over TCP until every peer has a complete copy.

---

## Common Pitfalls

### 1. Protocol Deviations

- **Message Format Errors:** Handshake messages must be exactly **32 bytes**. Actual messages must follow the specific format: `4-byte length + 1-byte type + variable payload`.
- **Request Strategy:** Unlike standard BitTorrent which uses "rarest-first," this project requires **random piece selection**.
- **No Pipelining:** You must wait to receive a `piece` message before sending the next `request`. This is simpler but different from how modern BitTorrent works.
### 2. Implementation Oversights

- **Missing Choke/Unchoke Logic:** The core of the project is the choking mechanism. You must reselect preferred neighbors every $p$ seconds and an optimistic neighbor every $m$ seconds.

- **Incorrect File Storage:** Peer-specific files must be stored in subdirectories named `peer_[peerID]` (e.g., `~/project/peer_1001/`).

- **Port Conflicts:** On shared department machines, **do not use port 6008**. Choose a unique port to avoid conflicts with other students.

### 3. Log Accuracy

- **Strict Logging:** Automated grading often relies on logs. You must generate specific log entries for every major event (connections, choking, receiving 'have', etc.) in the exact format required.
- **Piece Counts:** When a piece is downloaded, you must log the total number of pieces the peer now possesses.

---
## Important Things to Note

### Connection & Coordination

- **Connection Order:** A peer must initiate TCP connections to **all peers that started before it** in the `PeerInfo.cfg` list.
- **Termination:** The program shouldn't just stop when _you_ finish downloading; the process must terminate only when **all peers** in the network have the complete file.
- **Tie-breaking:** When selecting preferred neighbors based on download rates, if rates are equal, you must break the tie **randomly**.
---

# Implementation
### Work Breakdown
tbd...

## Existing Implementation

### `protocol.py`-

**Need to Implement**:
- [ ] Parse message based on type
- [ ] Create message based on type

- Defines the header and padding and builds the big endian byte structure for our communication protocol
- Also includes basic validation for length, header, and zero padding
- Creates both handshake and messages according to the following specs:

**Handshake:**
```
+-------------------------------+-------------------------------+  
|                                                               |  
|          Handshake Header (18 bytes)                          |  
|                "P2PFILESHARINGPROJ"                           |  
|                                                               |  
+-------------------------------+-------------------------------+  
|                                                               |  
|                Zero Bits (10 bytes)                           |  
|                     all 0s                                    |  
|                                                               |  
+-------------------------------+-------------------------------+  
|                       Peer ID (4 bytes)                       |  
|                    integer value                              |  
+---------------------------------------------------------------+  
Total Length: 32 bytes
```

**Message:**
```
+-------------------------------+  
| Message Length (4B) |  
+-------------------------------+  
| Message Type (1B) |  
+-------------------------------+  
| Payload (variable) |  
| |  
+-------------------------------+  
  
Message Length = bytes of (type + payload)  
Does NOT include the 4B length field itself
```

**Message Types:**
```
Choke (Type = 0)

+-------------------------------+  
| Message Length = 1            |  
+-------------------------------+  
| Message Type = 0 (choke)      |  
+-------------------------------+  
| Payload = none                |  
+-------------------------------+

---

Unchoke (Type = 1)

+-------------------------------+  
| Message Length = 1            |  
+-------------------------------+  
| Message Type = 1 (unchoke)    |  
+-------------------------------+  
| Payload = none                |  
+-------------------------------+

---

Interested (Type = 2)

+-------------------------------+  
| Message Length = 1            |  
+-------------------------------+  
| Message Type = 2 (interested) |  
+-------------------------------+  
| Payload = none                |  
+-------------------------------+

---

Not Interested (Type = 3)

+-----------------------------------+  
| Message Length = 1                |  
+-----------------------------------+  
| Message Type = 3 (not interested) |  
+-----------------------------------+  
| Payload = none                    |  
+-----------------------------------+

---

Have (Type = 4)

+-------------------------------+  
| Message Length = 5            |  
+-------------------------------+  
| Message Type = 4 (have)       |  
+-------------------------------+  
| Piece Index (4B)              |  
+-------------------------------+

---

Bitfield (Type = 5)

+-------------------------------+  
| Message Length = 1 + X        |  
+-------------------------------+  
| Message Type = 5 (bitfield)   |  
+-------------------------------+  
| Bitfield (X bytes)            |  
| each bit → piece ownership    |  
| high bit → low bit mapping    |  
+-------------------------------+


---

Request (Type = 6)

+-------------------------------+  
| Message Length = 5            |  
+-------------------------------+  
| Message Type = 6 (request)    |  
+-------------------------------+  
| Piece Index (4B)              |  
+-------------------------------+

---

Piece (Type = 7)

+-------------------------------+  
| Message Length = 1 + 4 + X    |  
+-------------------------------+  
| Message Type = 7 (piece)      |  
+-------------------------------+  
| Piece Index (4B)              |  
+-------------------------------+  
| Piece Content (X bytes)       |  
+-------------------------------+
```



### `log.py`-

**Need to Implement**:
- [ ] 

- Super basic logger that formats our log correctly when the `write()` function is called with our message

### `peerProcess.py`-

**Need to Implement**:
- [ ] find self entry in peers
- [ ] open server socket on self port
- [ ] connect to all predecessor peers
- [ ] exchange handshake then bitfield
- [ ] message receive loop
- [ ] choking/unchoking scheduler
- [ ] request/piece handling
- [ ] completion detection and shutdown 

- Barebones code as of now that just instantiates our logging and arg parser classes
- Loads `Common.cfg` and `PeerInfo.cfg` for later use

### `config.py`-

**Need to Implement**:
- [ ] 

- Creates the `CommonConfig` and `PeerInfo` config classes
- Has functionaly to load both the config and peer info files into actual objects