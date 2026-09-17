"""End-to-End integration test validating Data Router -> Data Parser -> Web Console pipeline."""

import json
import os
import shutil
import socket
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from Validation.Data_Parser.app.metrics.collector import ParserMetricsCollector
from Validation.Data_Parser.app.parsers.lrit import LRITParser
from Validation.Data_Parser.app.parsers.msis import MSISParser
from Validation.Data_Parser.app.parsers.nais import NAISParser
from Validation.Data_Parser.app.parsers.sais import SAISParser
from Validation.Data_Parser.app.parsers.vatms import VATMSParser
from Validation.Data_Parser.app.server.api_server import ParserAPIServer
from Validation.Data_Parser.app.server.endpoint import ParserEndpointServer
from Validation.Data_Router.app.config.loader import parse_raw_dict
from Validation.Data_Router.app.monitoring.metrics import MetricsCollector
from Validation.Data_Router.app.queue.manager import BoundedQueueManager
from Validation.Data_Router.app.reliability.state import FileStateStore
from Validation.Data_Router.app.routing.router import RoutingEngine
from Validation.Data_Router.app.sources.file_source import FileSourceManager
from Validation.Data_Router.app.transport.connection_manager import ParserConnectionManager
from Validation.Web_Console.app.parser_client import ParserClient
from Validation.Web_Console.app.router_client import RouterClient
from Validation.Web_Console.app.server import WebConsoleServer
from Validation.Web_Console.app.service_control.windows import WindowsDevelopmentController
from Validation.Web_Console.app.system_status import SystemStatusEvaluator


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestEndToEndPipeline(unittest.TestCase):
    """Verifies entire data lifecycle: File Inflow -> Router -> Parser TCP -> Parser Metrics -> Web Console."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="val_e2e_")
        self.inflow_dir = Path(self.temp_dir) / "INFLOW"
        self.sais_dir = self.inflow_dir / "SAIS_IOR"
        self.sais_dir.mkdir(parents=True, exist_ok=True)

        self.state_db = Path(self.temp_dir) / "state.db"
        self.router_log = Path(self.temp_dir) / "router.log"

        # Ports
        self.parser_tcp_port = find_free_port()
        self.parser_http_port = find_free_port()
        self.router_http_port = find_free_port()
        self.console_http_port = find_free_port()

        # 1. Start Parser Service
        self.parser_metrics = ParserMetricsCollector()
        self.parser_endpoint = ParserEndpointServer(
            name="SAIS",
            host="127.0.0.1",
            port=self.parser_tcp_port,
            parser=SAISParser(),
            metrics_collector=self.parser_metrics,
        )
        self.parser_endpoint.start()

        self.parser_api = ParserAPIServer(
            host="127.0.0.1",
            port=self.parser_http_port,
            metrics_collector=self.parser_metrics,
            endpoint_names=["SAIS"],
        )
        import threading
        self.p_api_thread = threading.Thread(target=self.parser_api.start, daemon=True)
        self.p_api_thread.start()

        # 2. Configure & Start Router Engine
        self.router_cfg_dict = {
            "data_inflow": {"base_dir": str(self.inflow_dir)},
            "parser_destinations": {
                "SAIS": {"host": "127.0.0.1", "port": self.parser_tcp_port, "framing": "ndjson"}
            },
            "sources": {
                "SAIS_IOR": {
                    "type": "file",
                    "folder": str(self.sais_dir),
                    "parser": "SAIS",
                    "enabled": True,
                    "poll_interval_seconds": 0.1,
                    "stability_window_seconds": 0.1,
                }
            },
            "queue": {"max_size": 1000, "worker_count": 2},
            "state": {"db_path": str(self.state_db)},
            "retry": {"max_attempts": 3, "initial_delay_seconds": 0.1, "max_delay_seconds": 1.0, "backoff_multiplier": 1.5},
            "monitoring": {"enabled": False},
        }
        self.router_config = parse_raw_dict(self.router_cfg_dict)
        self.state_store = FileStateStore(str(self.state_db))
        self.router_metrics = MetricsCollector()
        self.queue_mgr = BoundedQueueManager(self.router_config.queue)
        self.conn_mgr = ParserConnectionManager(self.router_config.parser_destinations)

        self.routing_engine = RoutingEngine(
            config=self.router_config,
            queue_manager=self.queue_mgr,
            connection_manager=self.conn_mgr,
            state_store=self.state_store,
            metrics_collector=self.router_metrics,
        )
        self.routing_engine.start()

        self.file_source_mgr = FileSourceManager(
            config=self.router_config.sources["SAIS_IOR"],
            base_inflow_dir=self.inflow_dir,
            routing_engine=self.routing_engine,
            state_store=self.state_store,
            metrics_collector=self.router_metrics,
        )
        self.file_source_mgr.start()

        # 3. Start Web Console
        self.router_client = RouterClient(
            api_url=f"http://127.0.0.1:{self.router_http_port}",
            config_path="Validation/Data_Router/config/sources.yaml",
            log_path=str(self.router_log),
            state_db_path=str(self.state_db),
            workspace_root=Path(__file__).resolve().parent.parent.parent,
        )
        self.parser_client = ParserClient(api_url=f"http://127.0.0.1:{self.parser_http_port}")
        self.sys_evaluator = SystemStatusEvaluator(
            router_client=self.router_client, parser_client=self.parser_client
        )
        self.service_ctrl = WindowsDevelopmentController()

        console_dir = Path(__file__).resolve().parent.parent / "Web_Console"
        self.web_server = WebConsoleServer(
            host="127.0.0.1",
            port=self.console_http_port,
            router_client=self.router_client,
            system_status=self.sys_evaluator,
            service_controller=self.service_ctrl,
            static_dir=console_dir / "app" / "static",
            template_path=console_dir / "app" / "templates" / "index.html",
            parser_client=self.parser_client,
        )
        self.web_thread = threading.Thread(target=self.web_server.start, daemon=True)
        self.web_thread.start()
        time.sleep(0.3)

    def tearDown(self):
        self.file_source_mgr.stop()
        self.routing_engine.stop()
        for c in self.conn_mgr._clients.values():
            c.disconnect()
        self.parser_endpoint.stop()
        self.parser_api.shutdown()
        self.web_server.shutdown()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_flow(self):
        # Ingest a real SAIS line
        raw_sais_data = "\\s:66,c:1782377468*4C\\!AIVDM,1,1,,B,177hgW001bWc5el;kRfmHl@<00SR,0*47\n"
        test_file = self.sais_dir / "e2e_sample.csv"
        test_file.write_text(raw_sais_data, encoding="utf-8")

        # Wait for file discovery -> stability window (0.1s) -> routing -> TCP delivery -> Parser ACK
        time.sleep(1.5)

        # 1. Verify Router state DB recorded delivery completion
        import sqlite3
        conn = sqlite3.connect(str(self.state_db))
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM file_states WHERE source = ? AND filename = ?", ("SAIS_IOR", "e2e_sample.csv"))
        row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row, "Record should exist in file_states database")
        self.assertIn(row[0], ("ACKNOWLEDGED", "PROCESSED"))

        # 2. Verify Parser processed the record
        p_metrics = self.parser_metrics.get_snapshot()
        self.assertEqual(p_metrics["messages_received"], 1)
        self.assertEqual(p_metrics["total_records_produced"], 1)
        self.assertEqual(p_metrics["source_distribution"]["SAIS_IOR"], 1)

        # 3. Verify Web Console exposes live status
        req = urllib.request.Request(f"http://127.0.0.1:{self.console_http_port}/api/system/status")
        with urllib.request.urlopen(req) as resp:
            sys_data = json.loads(resp.read().decode("utf-8"))
            modules = {m["id"]: m for m in sys_data["modules"]}
            self.assertEqual(modules["parser"]["status"], "RUNNING")
            self.assertEqual(modules["parser"]["health"], "HEALTHY")

        p_req = urllib.request.Request(f"http://127.0.0.1:{self.console_http_port}/api/parser/status")
        with urllib.request.urlopen(p_req) as resp:
            parser_status = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(parser_status["overall_status"], "OPERATIONAL")
            self.assertEqual(parser_status["metrics"]["total_records_produced"], 1)


if __name__ == "__main__":
    unittest.main()
