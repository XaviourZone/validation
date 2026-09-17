#!/usr/bin/env python3
"""Mock Data Parser Receiver simulating ports 10001-10005 with ACK responses."""

import argparse
import json
import logging
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from typing import List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ParserMock-%(port)s] %(message)s"
)


class MockParserEndpoint:
    """Simulates a downstream parser listening on a single TCP port."""

    def __init__(self, port: int, name: str, framing: str = "ndjson", failure_rate: float = 0.0):
        self.port = port
        self.name = name
        self.framing = framing
        self.failure_rate = failure_rate
        self.running = False
        self._server_sock: socket.socket = None
        self._thread: threading.Thread = None
        self.received_count = 0
        self.last_received_item = None

    def start(self) -> None:
        self.running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("127.0.0.1", self.port))
        self._server_sock.listen(10)
        self._server_sock.settimeout(1.0)

        self._thread = threading.Thread(
            target=self._accept_loop,
            name=f"MockParser-{self.port}",
            daemon=True,
        )
        self._thread.start()
        logging.info(f"Mock Parser '{self.name}' listening on 127.0.0.1:{self.port}", extra={"port": self.port})

    def stop(self) -> None:
        self.running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)

    def _accept_loop(self) -> None:
        while self.running:
            try:
                client_sock, addr = self._server_sock.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    daemon=True,
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, client_sock: socket.socket, addr) -> None:
        client_sock.settimeout(30.0)
        buffer = bytearray()

        try:
            while self.running:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)

                if self.framing == "length_prefixed":
                    while len(buffer) >= 4:
                        msg_len = struct.unpack(">I", buffer[:4])[0]
                        if len(buffer) < 4 + msg_len:
                            break
                        msg_bytes = buffer[4:4 + msg_len]
                        buffer = buffer[4 + msg_len:]
                        self._process_message(client_sock, msg_bytes)
                else:
                    # Newline delimited
                    while b"\n" in buffer:
                        idx = buffer.index(b"\n")
                        line_bytes = buffer[:idx]
                        buffer = buffer[idx + 1:]
                        if line_bytes:
                            self._process_message(client_sock, line_bytes)

        except (socket.timeout, ConnectionResetError, OSError):
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _process_message(self, client_sock: socket.socket, raw_bytes: bytearray) -> None:
        try:
            envelope = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            logging.error(f"Received malformed JSON: {e}", extra={"port": self.port})
            return

        msg_id = envelope.get("message_id", "unknown")
        source = envelope.get("source", "unknown")
        filename = envelope.get("filename", "")
        payload_len = len(envelope.get("payload", ""))

        self.received_count += 1
        self.last_received_item = envelope

        logging.info(
            f"RECEIVED message_id={msg_id} source={source} file={filename} payload_bytes={payload_len}",
            extra={"port": self.port}
        )

        # Send ACK
        ack_payload = {
            "message_id": msg_id,
            "status": "ACK",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        ack_bytes = json.dumps(ack_payload).encode("utf-8")
        if self.framing == "length_prefixed":
            header = struct.pack(">I", len(ack_bytes))
            client_sock.sendall(header + ack_bytes)
        else:
            client_sock.sendall(ack_bytes + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-port Mock Data Parser Receiver")
    parser.add_argument(
        "--ports",
        nargs="+",
        type=int,
        default=[10001, 10002, 10003, 10004, 10005],
        help="Ports to bind mock parsers (default: 10001-10005)"
    )
    args = parser.parse_args()

    port_names = {
        10001: "SAIS Parser",
        10002: "MSIS Parser",
        10003: "LRIT Parser",
        10004: "VATMS Parser",
        10005: "NAIS Parser",
    }

    endpoints: List[MockParserEndpoint] = []
    for port in args.ports:
        name = port_names.get(port, f"Parser-{port}")
        ep = MockParserEndpoint(port=port, name=name)
        ep.start()
        endpoints.append(ep)

    logging.info("Mock parsers are RUNNING. Press Ctrl+C to stop.", extra={"port": "ALL"})
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logging.info("Stopping mock parsers...", extra={"port": "ALL"})
        for ep in endpoints:
            ep.stop()
        logging.info("Mock parsers stopped.", extra={"port": "ALL"})


if __name__ == "__main__":
    main()
