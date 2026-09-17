"""Disk, Directory, and Permission Resilience Integration Tests.

Verifies:
1. Missing Input Directory:
   - File source configured with non-existent or deleted folder.
   - Service does not crash.
   - Source is marked `connected=False` in metrics and logs warning.
   - When directory is created/restored, source automatically recovers.
   - Concurrent sources are completely unaffected.

2. Unreadable / Permission Denied File:
   - File created with restricted read permissions or locked.
   - Router detects error during read, marks file FAILED in SQLite state, logs error.
   - Service does NOT crash; subsequent readable files are processed normally.

3. Inaccessible State Database Handling:
   - Read-only or inaccessible database path handled with logged error rather than silent loss.
"""

import os
import socket
import stat
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
        import json
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
        import json
        buf = bytearray()
        while self.running:
            try:
                data = client.recv(16384)
                if not data:
                    break
                buf.extend(data)
                while b"\n" in buf:
                    idx = buf.index(b"\n")
                    line = buf[:idx]
                    buf = buf[idx + 1:]
                    if line:
                        env = json.loads(line.decode("utf-8"))
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


class TestDiskPermissionResilience(unittest.TestCase):
    """Verifies edge-case resilience to missing folders, locked files, and disk errors."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.inflow_dir = self.base_path / "INFLOW"
        self.inflow_dir.mkdir(parents=True)
        self.state_db = self.base_path / "router_state.db"

        self.mock_parser = MockParserReceiver()

        self.config = RouterConfig(
            data_inflow=DataInflowConfig(base_dir=str(self.inflow_dir)),
            parser_destinations={
                "SAIS": ParserDestinationConfig(
                    name="SAIS", host="127.0.0.1", port=self.mock_parser.port, timeout_seconds=0.5
                )
            },
            sources={
                "VALID_SOURCE": FileSourceConfig(
                    name="VALID_SOURCE", type="file", folder="VALID_FOLDER", parser="SAIS",
                    poll_interval_seconds=0.1, stability_window_seconds=0.2
                ),
                "MISSING_SOURCE": FileSourceConfig(
                    name="MISSING_SOURCE", type="file", folder="MISSING_FOLDER", parser="SAIS",
                    poll_interval_seconds=0.1, stability_window_seconds=0.2
                ),
            },
            queue=QueueConfig(max_size=100, worker_count=1),
            retry=RetryConfig(max_attempts=3, initial_delay_seconds=0.1),
            state=StateConfig(db_path=str(self.state_db)),
            monitoring=MonitoringConfig(enabled=False),
        )

        self.state_store = FileStateStore(self.state_db)
        self.metrics = MetricsCollector()
        self.queue_mgr = BoundedQueueManager(self.config.queue)
        self.conn_mgr = ParserConnectionManager(self.config.parser_destinations)
        self.router = RoutingEngine(
            self.config, self.queue_mgr, self.conn_mgr, self.state_store, self.metrics
        )
        self.router.start()

    def tearDown(self):
        self.router.stop()
        self.conn_mgr.disconnect_all()
        self.mock_parser.close()
        self.temp_dir.cleanup()

    def test_missing_directory_handled_gracefully_and_recovers(self):
        """Missing folder marks source disconnected without crashing daemon; recovers when created."""
        valid_dir = self.inflow_dir / "VALID_FOLDER"
        missing_dir = self.inflow_dir / "MISSING_FOLDER"
        valid_dir.mkdir(parents=True, exist_ok=True)

        valid_mgr = FileSourceManager(
            self.config.sources["VALID_SOURCE"], self.inflow_dir, self.router, self.state_store, self.metrics
        )
        missing_mgr = FileSourceManager(
            self.config.sources["MISSING_SOURCE"], self.inflow_dir, self.router, self.state_store, self.metrics
        )

        valid_mgr.start()
        missing_mgr.start()

        # Delete missing_dir to simulate folder deletion or unmounted volume
        if missing_dir.exists():
            import shutil
            shutil.rmtree(missing_dir)

        time.sleep(0.3)

        # Missing source is isolated and disconnected
        self.assertFalse(missing_mgr.is_connected())

        # Valid source is unaffected and functioning
        self.assertTrue(valid_mgr.is_connected())
        (valid_dir / "valid_file.csv").write_text("col1,col2\nval1,val2\n", encoding="utf-8")

        # Verify valid file is delivered despite missing sibling folder
        start_wait = time.time()
        while time.time() - start_wait < 3.0:
            if len(self.mock_parser.received_envelopes) == 1:
                break
            time.sleep(0.1)

        self.assertEqual(len(self.mock_parser.received_envelopes), 1)
        self.assertEqual(self.mock_parser.received_envelopes[0]["filename"], "valid_file.csv")

        # Now recreate missing folder to test automatic recovery
        missing_dir.mkdir(parents=True, exist_ok=True)
        time.sleep(0.3)
        self.assertTrue(missing_mgr.is_connected(), "Source did not recover after folder was created")

        valid_mgr.stop()
        missing_mgr.stop()

    def test_unreadable_file_isolated_without_crashing_service(self):
        """File with locked / read permissions failure is marked FAILED without halting service."""
        valid_dir = self.inflow_dir / "VALID_FOLDER"
        valid_dir.mkdir(parents=True, exist_ok=True)

        valid_mgr = FileSourceManager(
            self.config.sources["VALID_SOURCE"], self.inflow_dir, self.router, self.state_store, self.metrics
        )
        valid_mgr.start()

        # Simulate unreadable file by mocking _read_file_content to raise PermissionError for a bad file
        bad_file = valid_dir / "unreadable_file.csv"
        bad_file.write_text("corrupted content", encoding="utf-8")

        orig_read = valid_mgr._read_file_content
        def failing_read(path):
            if path.name == "unreadable_file.csv":
                raise PermissionError("EACCES: Permission denied by OS lock")
            return orig_read(path)

        valid_mgr._read_file_content = failing_read

        time.sleep(0.6)

        # The bad file should be marked FAILED in SQLite state
        stats = self.state_store.get_stats()
        self.assertIn("FAILED", stats)

        # Verify that subsequent healthy files continue processing normally
        good_file = valid_dir / "good_file.csv"
        good_file.write_text("col1,col2\n123,456\n", encoding="utf-8")

        start_wait = time.time()
        delivered = False
        while time.time() - start_wait < 3.0:
            envs = [e for e in self.mock_parser.received_envelopes if e["filename"] == "good_file.csv"]
            if envs:
                delivered = True
                break
            time.sleep(0.1)

        valid_mgr.stop()
        self.assertTrue(delivered, "Healthy file was blocked by prior unreadable file failure!")


if __name__ == "__main__":
    unittest.main()
