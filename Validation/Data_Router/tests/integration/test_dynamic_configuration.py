"""Dynamic Configuration Verification Test.

Verifies that adding:
1. A new folder source (TEST_SOURCE_FOLDER)
2. A new network stream source (TEST_SOURCE_TCP)

via YAML configuration file alone requires ZERO Python source code modifications.
Loads new YAML configuration, initializes service components, routes data to downstream parser,
and verifies correct envelope creation, provenance labeling, delivery, and ACK.
"""

import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
import yaml

from Validation.Data_Router.app.config.loader import load_config
from Validation.Data_Router.app.monitoring.metrics import MetricsCollector
from Validation.Data_Router.app.queue.manager import BoundedQueueManager
from Validation.Data_Router.app.reliability.state import FileState, FileStateStore
from Validation.Data_Router.app.routing.router import RoutingEngine
from Validation.Data_Router.app.sources.file_source import FileSourceManager
from Validation.Data_Router.app.sources.tcp_source import TCPSourceManager
from Validation.Data_Router.app.transport.connection_manager import ParserConnectionManager


class MockDynamicParser:
    """Mock parser receiving data from dynamically configured sources."""

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


class MockDynamicFeedServer:
    """Mock TCP feed server streaming sample lines for dynamic source test."""

    def __init__(self, port: int = 0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(5)
        self.sock.settimeout(0.5)
        self.running = True
        self.clients = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self.running:
            try:
                client, _ = self.sock.accept()
                with self._lock:
                    self.clients.append(client)
            except socket.timeout:
                continue
            except OSError:
                break

    def broadcast_line(self, line: str):
        data = (line.rstrip("\r\n") + "\n").encode("utf-8")
        with self._lock:
            for c in list(self.clients):
                try:
                    c.sendall(data)
                except Exception:
                    self.clients.remove(c)

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


class TestDynamicConfiguration(unittest.TestCase):
    """Verifies completely dynamic addition of folder and TCP sources via YAML configuration alone."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.inflow_dir = self.base_path / "INFLOW"
        self.inflow_dir.mkdir(parents=True)
        self.state_db = self.base_path / "router_state.db"
        self.yaml_config_path = self.base_path / "sources.yaml"

        self.mock_parser = MockDynamicParser()
        self.mock_feed = MockDynamicFeedServer()

        # Write YAML defining newly introduced sources
        config_dict = {
            "data_inflow": {
                "base_dir": str(self.inflow_dir)
            },
            "parser_destinations": {
                "TARGET_PARSER": {
                    "host": "127.0.0.1",
                    "port": self.mock_parser.port,
                    "framing": "ndjson",
                    "timeout_seconds": 1.0,
                    "keep_alive": True,
                }
            },
            "sources": {
                "TEST_SOURCE_FOLDER": {
                    "type": "file",
                    "folder": "DYNAMIC_FOLDER",
                    "parser": "TARGET_PARSER",
                    "enabled": True,
                    "poll_interval_seconds": 0.1,
                    "stability_window_seconds": 0.2,
                    "file_patterns": ["*.csv", "*.txt"],
                },
                "TEST_SOURCE_TCP": {
                    "type": "tcp",
                    "remote_host": "127.0.0.1",
                    "remote_port": self.mock_feed.port,
                    "parser": "TARGET_PARSER",
                    "enabled": True,
                    "reconnect_initial_delay": 0.2,
                }
            },
            "queue": {
                "max_size": 100,
                "worker_count": 2,
            },
            "retry": {
                "max_attempts": 3,
                "initial_delay_seconds": 0.1,
            },
            "state": {
                "db_path": str(self.state_db)
            },
            "monitoring": {
                "enabled": False,
            }
        }

        with open(self.yaml_config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f)

    def tearDown(self):
        self.mock_parser.close()
        self.mock_feed.close()
        self.temp_dir.cleanup()

    def test_configuration_only_addition_works_end_to_end(self):
        """Zero Python code changes: dynamic folder and TCP sources route correctly."""
        # 1. Load configuration strictly from YAML file
        loaded_config = load_config(self.yaml_config_path)

        state_store = FileStateStore(self.state_db)
        metrics = MetricsCollector()
        queue_mgr = BoundedQueueManager(loaded_config.queue)
        conn_mgr = ParserConnectionManager(loaded_config.parser_destinations)
        router = RoutingEngine(loaded_config, queue_mgr, conn_mgr, state_store, metrics)

        # Instantiate sources directly from configuration dictionary
        sources = {}
        for src_name, src_cfg in loaded_config.sources.items():
            if src_cfg.type == "file":
                sources[src_name] = FileSourceManager(
                    src_cfg, Path(loaded_config.data_inflow.base_dir), router, state_store, metrics
                )
            elif src_cfg.type == "tcp":
                sources[src_name] = TCPSourceManager(src_cfg, router, metrics)

        router.start()
        for src in sources.values():
            src.start()

        time.sleep(0.5)

        # 2. Test dynamic folder source
        dynamic_folder = self.inflow_dir / "DYNAMIC_FOLDER"
        test_file = dynamic_folder / "dynamic_sample.csv"
        file_payload = "colA,colB\nval1,val2\n"
        test_file.write_text(file_payload, encoding="utf-8")

        # 3. Test dynamic TCP source
        tcp_line = "!DYNAMIC_NMEA,1,2,3*FF"
        self.mock_feed.broadcast_line(tcp_line)

        # 4. Await delivery of both
        start_wait = time.time()
        while time.time() - start_wait < 5.0:
            if len(self.mock_parser.received_envelopes) >= 2:
                break
            time.sleep(0.1)

        for src in sources.values():
            src.stop()
        router.stop()
        conn_mgr.disconnect_all()

        envelopes = self.mock_parser.received_envelopes
        self.assertEqual(len(envelopes), 2, f"Expected 2 envelopes, received {len(envelopes)}")

        sources_seen = {e["source"] for e in envelopes}
        self.assertIn("TEST_SOURCE_FOLDER", sources_seen)
        self.assertIn("TEST_SOURCE_TCP", sources_seen)

        folder_env = [e for e in envelopes if e["source"] == "TEST_SOURCE_FOLDER"][0]
        self.assertEqual(folder_env["payload"], file_payload)
        self.assertEqual(folder_env["filename"], "dynamic_sample.csv")

        tcp_env = [e for e in envelopes if e["source"] == "TEST_SOURCE_TCP"][0]
        self.assertEqual(tcp_env["payload"], tcp_line)


if __name__ == "__main__":
    unittest.main()
