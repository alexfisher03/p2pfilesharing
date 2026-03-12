import socket
import threading
import protocol


class NetworkManager:

    def __init__(self, self_peer_id, self_port, on_connected, on_message, on_disconnected):
        self.self_peer_id = self_peer_id        # who am i
        self.self_port = self_port              # what port do i listen on
        self.on_connected = on_connected        # callback to developer C
        self.on_message = on_message            # callback to developer C
        self.on_disconnected = on_disconnected  # callback to developer C
        self.connections = {}                   # peer_id -> (sock, lock)
        self._server_sock = None                # set later in start_server
        self._shutdown = threading.Event()      # flip this to stop all loops

    # open listener and start accept loop thread
    def start_server(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("", self.self_port))
        self._server_sock.listen()
        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()

    # loops calling accept() and spawns a thread per incoming connection
    def _accept_loop(self):
        while not self._shutdown.is_set():
            try:
                sock, _ = self._server_sock.accept()
            except OSError:
                break
            t = threading.Thread(target=self._handle_incoming, args=(sock,), daemon=True)
            t.start()

    # called when someone connects TO us — they send handshake first
    def _handle_incoming(self, sock):
        try:
            remote_peer_id = protocol.recv_handshake(sock)
            sock.sendall(protocol.make_handshake(self.self_peer_id))
        except Exception:
            sock.close()
            return
        lock = threading.Lock()
        self.connections[remote_peer_id] = (sock, lock)
        self.on_connected(remote_peer_id, incoming=True)
        t = threading.Thread(target=self._listen_loop, args=(remote_peer_id, sock), daemon=True)
        t.start()

    # called when WE connect to someone — we send handshake first
    def connect_to_peer(self, remote_peer_id, host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
            sock.sendall(protocol.make_handshake(self.self_peer_id))
            protocol.recv_handshake(sock)
        except Exception:
            sock.close()
            return
        lock = threading.Lock()
        self.connections[remote_peer_id] = (sock, lock)
        self.on_connected(remote_peer_id, incoming=False)
        t = threading.Thread(target=self._listen_loop, args=(remote_peer_id, sock), daemon=True)
        t.start()

    # one of these runs per connected peer — blocks waiting for messages
    def _listen_loop(self, remote_peer_id, sock):
        while not self._shutdown.is_set():
            try:
                message = protocol.recv_message(sock)
                self.on_message(remote_peer_id, message)
            except Exception:
                self._disconnect(remote_peer_id)
                break

    # send one message to one peer
    def send_message(self, remote_peer_id, message):
        if remote_peer_id not in self.connections:
            return
        sock, lock = self.connections[remote_peer_id]
        with lock:
            try:
                sock.sendall(protocol.make_message(message.message_type, message.payload))
            except Exception:
                self._disconnect(remote_peer_id)

    # send a message to all connected peers, optionally skipping some
    def broadcast_message(self, message, exclude=None):
        for peer_id in list(self.connections):
            if exclude and peer_id in exclude:
                continue
            self.send_message(peer_id, message)

    # clean up one peer connection and notify developer C
    def _disconnect(self, remote_peer_id):
        if remote_peer_id not in self.connections:
            return
        sock, _ = self.connections.pop(remote_peer_id)
        try:
            sock.close()
        except Exception:
            pass
        self.on_disconnected(remote_peer_id)

    # close everything
    def shutdown(self):
        self._shutdown.set()
        for peer_id in list(self.connections):
            self._disconnect(peer_id)
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
