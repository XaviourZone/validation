#!/usr/bin/env python3
"""Mock TCP Source Server simulating live feeds (VATMS East/West, NAIS)."""

import argparse
import logging
import socket
import threading
import time
from pathlib import Path
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MockFeed-%(port)s] %(message)s")


class MockFeedServer:
    """Listens on a port and broadcasts streaming feed lines to connected Router clients."""

    def __init__(self, port: int, name: str, sample_file: Path, interval: float = 1.0):
        self.port = port
        self.name = name
        self.sample_file = Path(sample_file)
        self.interval = interval
        self.running = False
        self._server_sock: socket.socket = None
        self._thread: threading.Thread = None
        self._clients: List[socket.socket] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self.running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("127.0.0.1", self.port))
        self._server_sock.listen(5)
        self._server_sock.settimeout(1.0)

        self._thread = threading.Thread(target=self._run, name=f"MockFeed-{self.port}", daemon=True)
        self._thread.start()
        logging.info(f"Feed '{self.name}' listening on 127.0.0.1:{self.port}", extra={"port": self.port})

    def stop(self) -> None:
        self.running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        with self._lock:
            for c in self._clients:
                try:
                    c.close()
                except Exception:
                    pass
            self._clients.clear()

    def _run(self) -> None:
        # Load sample lines
        lines: List[str] = []
        if self.sample_file.exists():
            with open(self.sample_file, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip()]

        if not lines:
            lines = [f"$MOCK,SIMULATED_FEED,{self.name},LINE_{i}*00" for i in range(100)]

        line_idx = 0

        while self.running:
            # Check for new incoming connections
            try:
                client_sock, addr = self._server_sock.accept()
                with self._lock:
                    self._clients.append(client_sock)
                logging.info(f"Accepted connection from Router at {addr}", extra={"port": self.port})
            except socket.timeout:
                pass
            except OSError:
                break

            # Broadcast current line to all connected clients
            if lines and self._clients:
                current_line = lines[line_idx % len(lines)] + "\n"
                raw_bytes = current_line.encode("utf-8")
                line_idx += 1

                with self._lock:
                    dead_clients = []
                    for c in self._clients:
                        try:
                            c.sendall(raw_bytes)
                        except (socket.error, OSError):
                            dead_clients.append(c)
                    for dc in dead_clients:
                        self._clients.remove(dc)
                        try:
                            dc.close()
                        except Exception:
                            pass

            time.sleep(self.interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate remote TCP data feeds (VATMS, NAIS)")
    parser.add_argument("--port", type=int, default=20001, help="Port to bind feed server")
    parser.add_argument("--name", default="VATMS_EAST", help="Feed identifier name")
    parser.add_argument("--sample", default="Validation/SAMPLE_DATA/VATMS/VATMS_EAST/vatms_east.txt", help="Sample data path")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between lines")
    args = parser.parse_args()

    feed = MockFeedServer(
        port=args.port,
        name=args.name,
        sample_file=Path(args.sample),
        interval=args.interval,
    )
    feed.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        feed.stop()


if __name__ == "__main__":
    main()
