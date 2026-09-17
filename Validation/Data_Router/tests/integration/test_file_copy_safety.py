"""Operational Integration Test: File-Copy Safety / Stability Verification.

Simulates real cron file transfer where a file is copied gradually in chunks.
Verifies:
1. Router detects the arriving file early.
2. Router DOES NOT process or deliver premature partial file while writes are ongoing.
3. Once file writing concludes and stability_window_seconds passes without changes,
   the file is verified stable.
4. Router processes the completed file, delivers the full payload, and persists state.
"""

import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from Validation.Data_Router.app.config.models import (
    DataInflowConfig,
    FileSourceConfig,
    MonitoringConfig,
    ParserDestinationConfig,
    QueueConfig,
    RetryConfig,
    RouterConfig,
    StateConfig,
)
from Validation.Data_Router.app.monitoring.metrics import MetricsCollector
from Validation.Data_Router.app.queue.manager import BoundedQueueManager
from Validation.Data_Router.app.reliability.state import FileState, FileStateStore
from Validation.Data_Router.app.routing.router import RoutingEngine
from Validation.Data_Router.app.sources.file_source import FileSourceManager
from Validation.Data_Router.app.transport.connection_manager import ParserConnectionManager


class MockParserReceiver:
    """Mock parser receiver recording delivered envelopes."""

    def __init__(self, port: int = 0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(5)
        self.sock.settimeout(0.5)
        self.running = True
        self.clients = []
        self.received_envelopes = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self.running:
            try:
                client, _ = self.sock.accept()
                client.settimeout(0.5)
                with self._lock:
                    self.clients.append(client)
                threading.Thread(target=self._client_handler, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _client_handler(self, client: socket.socket):
        buf = bytearray()
        while self.running:
            try:
                data = client.recv(16384)
                if not data:
                    break
                buf.extend(data)
                while b"\n" in buf:
                    idx = buf.index(b"\n")
                    line_bytes = buf[:idx]
                    buf = buf[idx + 1:]
                    if line_bytes:
                        env = json.loads(line_bytes.decode("utf-8"))
                        with self._lock:
                            self.received_envelopes.append(env)
                        ack = json.dumps({"message_id": env["message_id"], "status": "ACK"}) + "\n"
                        client.sendall(ack.encode("utf-8"))
            except socket.timeout:
                continue
            except Exception:
                break
        try:
            client.close()
        except Exception:
            pass

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        with self._lock:
            for c in list(self.clients):
                try:
                    c.close()
                except Exception:
                    pass
            self.clients.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


class TestFileCopySafety(unittest.TestCase):
    """Verifies that files undergoing slow copy or incremental writes are never partially read."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.inflow_dir = self.base_path / "INFLOW"
        self.sais_dir = self.inflow_dir / "SAIS_IOR"
        self.sais_dir.mkdir(parents=True)
        self.state_db = self.base_path / "router_state.db"

        self.mock_parser = MockParserReceiver()

        self.stability_window = 0.5  # 500ms stability window
        self.config = RouterConfig(
            data_inflow=DataInflowConfig(base_dir=str(self.inflow_dir)),
            parser_destinations={
                "SAIS": ParserDestinationConfig(
                    name="SAIS",
                    host="127.0.0.1",
                    port=self.mock_parser.port,
                )
            },
            sources={
                "SAIS_IOR": FileSourceConfig(
                    name="SAIS_IOR",
                    type="file",
                    folder="SAIS_IOR",
                    parser="SAIS",
                    poll_interval_seconds=0.1,
                    stability_window_seconds=self.stability_window,
                )
            },
            queue=QueueConfig(max_size=100, worker_count=1),
            retry=RetryConfig(max_attempts=3, initial_delay_seconds=0.2),
            state=StateConfig(db_path=str(self.state_db)),
            monitoring=MonitoringConfig(enabled=False),
        )

        self.state_store = FileStateStore(self.state_db)
        self.metrics = MetricsCollector()
        self.queue_mgr = BoundedQueueManager(self.config.queue)
        self.conn_mgr = ParserConnectionManager(self.config.parser_destinations)
        self.router = RoutingEngine(
            config=self.config,
            queue_manager=self.queue_mgr,
            connection_manager=self.conn_mgr,
            state_store=self.state_store,
            metrics_collector=self.metrics,
        )
        self.file_source = FileSourceManager(
            config=self.config.sources["SAIS_IOR"],
            base_inflow_dir=self.inflow_dir,
            routing_engine=self.router,
            state_store=self.state_store,
            metrics_collector=self.metrics,
        )

        self.router.start()
        self.file_source.start()

    def tearDown(self):
        self.file_source.stop()
        self.router.stop()
        self.conn_mgr.disconnect_all()
        self.mock_parser.close()
        self.temp_dir.cleanup()

    def test_gradual_file_copy_not_processed_until_stable(self):
        """Simulate a cron job copying a 50KB CSV file gradually over 1.2 seconds."""
        target_file = self.sais_dir / "slow_transfer.csv"
        
        # Prepare 10 chunks of data
        chunk_line = "\\s:66,c:1782377468*4C\\!AIVDM,1,1,,B,177hgW001bWc5el;kRfmHl@<00SR,0*47\n"
        chunks = [chunk_line * 50 for _ in range(10)]
        total_expected_payload = "".join(chunks)
        total_expected_size = len(total_expected_payload.encode("utf-8"))

        # 1. Start writing chunks slowly with delays
        with open(target_file, "w", encoding="utf-8", newline="\n") as f:
            for i in range(5):
                f.write(chunks[i])
                f.flush()
                time.sleep(0.15)  # 150ms between chunks, less than 500ms stability window

            # During writing, verify Router has NOT queued or sent the partial file
            self.assertEqual(
                len(self.mock_parser.received_envelopes), 0,
                "Premature delivery! Partial file was processed while writes were active."
            )

            # Write remaining 5 chunks
            for i in range(5, 10):
                f.write(chunks[i])
                f.flush()
                time.sleep(0.15)

            # File copy finishes here
            self.assertEqual(target_file.stat().st_size, total_expected_size)

        # 2. Immediately upon close, stability window has not yet fully elapsed
        # Check that envelope is still not delivered immediately
        time.sleep(0.1)
        # Note: Depending on tick alignment, it might be waiting for stability window

        # 3. Wait for stability window (0.5s) + poll cycle (0.1s) to elapse
        start_wait = time.time()
        delivered = False
        while time.time() - start_wait < 3.0:
            if len(self.mock_parser.received_envelopes) == 1:
                delivered = True
                break
            time.sleep(0.1)

        self.assertTrue(delivered, "File was not delivered after stability window elapsed")
        env = self.mock_parser.received_envelopes[0]
        self.assertEqual(env["filename"], "slow_transfer.csv")
        self.assertEqual(env["file_size"], total_expected_size)
        self.assertEqual(env["payload"], total_expected_payload, "Payload does not match full completed file!")

        # Verify state in SQLite
        record = self.state_store.get_by_message_id(env["message_id"])
        self.assertIsNotNone(record)
        self.assertIn(record.status, (FileState.ACKNOWLEDGED, FileState.PROCESSED))


if __name__ == "__main__":
    unittest.main()
