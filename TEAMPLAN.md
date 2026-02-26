# P2P File Sharing Project (Team Plan)

## Goal
Build a simplified BitTorrent-style P2P file sharing system in Python that:
- runs locally across multiple processes on one machine
- then runs across three laptops
- follows assignment protocol and logging requirements

## Team Split Plan

## Developer A (Protocol Owner)
Owns: `protocol.py`

Responsibilities:
- handshake encode/decode
- actual message encode/decode
- socket-safe receive helpers (`read_exact`, `recv_message`)
- payload helpers (`have`, `request`, `piece`)
- `MessageType` definitions
- protocol contract documentation for team integration

Deliverables:
- working `protocol.py`
- `docs/protocol_overview.md`
- `docs/protocol_api.md`

## Developer B (Networking Owner)
Owns: `networking.py` (new file)

Responsibilities:
- listener socket and accept loop
- outgoing connections to predecessor peers
- handshake exchange using `protocol.py`
- per-peer receive loop
- send API / broadcast API
- disconnect handling and cleanup
- callback interface into peer process

Deliverables:
- working `networking.py`
- `docs/networking_overview.md`
- `docs/networking_api.md`

## Developer C (Peer Process Owner)
Owns: `peerProcess.py` and runtime behavior

Responsibilities:
- config usage and startup orchestration
- local and neighbor state management
- interested/not interested logic
- choke/unchoke logic
- request/piece/have handling
- completion detection
- logging integration
- file piece read/write integration

Deliverables:
- working `peerProcess.py`
- `docs/peerprocess_overview.md`
- `docs/peerprocess_api.md`

## Interface Boundaries (Must Stay Strict)

## `protocol.py` owns
- all binary byte format rules
- all packing/unpacking logic
- all frame validation

## `networking.py` owns
- sockets
- threads for send/receive and accept loops
- connection lifecycle
- callbacking decoded messages to peer process

## `peerProcess.py` owns
- protocol semantics
- state transitions
- scheduling logic
- piece selection and file transfer decisions

## Shared Rules
- no duplicate protocol parsing code outside `protocol.py`
- no raw `sock.recv()` inside `peerProcess.py`
- no choke/unchoke decisions inside `networking.py`

## Integration Contract (Recommended)

## Networking -> PeerProcess callbacks
- `on_peer_connected(remote_peer_id: int, incoming: bool) -> None`
- `on_message(remote_peer_id: int, message: Message) -> None`
- `on_peer_disconnected(remote_peer_id: int) -> None`

## PeerProcess -> Networking calls
- `start_server() -> None`
- `connect_to_peer(remote_peer_id: int, host: str, port: int) -> None`
- `send_message(remote_peer_id: int, message: Message) -> None`
- `broadcast_message(message: Message, exclude: set[int] | None = None) -> None`
- `shutdown() -> None`

## Milestones

## Milestone 1: Local startup + handshake (2 peers)
Success criteria:
- peers connect on `localhost`
- handshake succeeds both directions
- connection logs are written

## Milestone 2: Bitfield + interest flow
Success criteria:
- peers exchange `bitfield`
- non-seed sends `interested`
- logs show interested/not interested events

## Milestone 3: Temporary piece transfer (simple unchoke)
Success criteria:
- seed sends `unchoke` (temporary logic allowed)
- leecher requests and receives at least one piece
- `have` is broadcast after piece receipt

## Milestone 4: Full local swarm on one machine
Success criteria:
- all local peers complete on small config
- completion logs generated

## Milestone 5: Cross-laptop test (3 laptops)
Success criteria:
- peers connect using laptop IPs/hostnames
- end-to-end file distribution works
- logs generated on all machines

## Local Development Setup (Recommended)
Use a local `PeerInfo.cfg` for testing:
- `1001 localhost 6001 1`
- `1002 localhost 6002 0`
- `1003 localhost 6003 0`

Notes:
- use unique ports on one machine
- place full seed file in `peer_1001/`
- start processes in `PeerInfo.cfg` order

## Suggested Workflow
- Build and test each module independently
- Integrate at handshake stage first
- Integrate bitfield/interest second
- Integrate piece transfer third
- Implement full choke/unchoke policy after transfer works

## Definition of Done (Project)
- protocol follows assignment spec exactly
- required logs are generated correctly
- peers terminate when all peers complete file
- works locally and across three laptops
