"""Integration test: Duplicate file prevention across scans and service restarts."""

import tempfile
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
from Validation.Data_Router.app.reliability.state import FileStateStore
from Validation.Data_Router.app.routing.router import RoutingEngine
from Validation.Data_Router.app.sources.file_source import FileSourceManager
from Validation.Data_Router.app.transport.connection_manager import ParserConnectionManager
from .test_file_routing import MockSingleParser


class TestDuplicatePreventionIntegration(unittest.TestCase):
    """Ensure already acknowledged files are never re-sent."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.inflow_dir = self.base_path / "INFLOW"
        self.msis_dir = self.inflow_dir / "MSIS"
        self.msis_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_path / "router_state.db"

        self.parser = MockSingleParser()

        self.config = RouterConfig(
            data_inflow=DataInflowConfig(base_dir=str(self.inflow_dir)),
            parser_destinations={
                "MSIS": ParserDestinationConfig(
                    name="MSIS",
                    host="127.0.0.1",
                    port=self.parser.port,
                    framing="ndjson",
                    timeout_seconds=2.0,
                )
            },
            sources={
                "MSIS": FileSourceConfig(
                    name="MSIS",
                    type="file",
                    folder="MSIS",
                    parser="MSIS",
                    enabled=True,
                    poll_interval_seconds=0.2,
                    stability_window_seconds=0.3,
                )
            },
            retry=RetryConfig(max_attempts=2),
            queue=QueueConfig(max_size=100, worker_count=1),
            monitoring=MonitoringConfig(enabled=False),
            state=StateConfig(db_path=str(self.db_path)),
        )

        self.state_store = FileStateStore(self.db_path)
        self.metrics = MetricsCollector()
        self.metrics.register_source("MSIS")
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
            config=self.config.sources["MSIS"],
            base_inflow_dir=self.inflow_dir,
            routing_engine=self.router,
            state_store=self.state_store,
            metrics_collector=self.metrics,
        )

    def tearDown(self):
        self.file_source.stop()
        self.router.stop()
        self.parser.close()
        self.temp_dir.cleanup()

    def test_duplicate_file_skipped_after_restart(self):
        # 1. Process initial file
        self.router.start()
        self.file_source.start()

        test_file = self.msis_dir / "msis_batch_01.csv"
        test_file.write_text("mmsi,lat,lon\n219023392,55.216,11.742\n", encoding="utf-8")

        # Wait for delivery
        time.sleep(2.0)
        self.assertEqual(len(self.parser.received_envelopes), 1)

        # 2. Simulate restart of router and file source
        self.file_source.stop()
        self.router.stop()

        # Re-initialize file source and router reusing same SQLite state
        new_queue_mgr = BoundedQueueManager(self.config.queue)
        new_router = RoutingEngine(
            config=self.config,
            queue_manager=new_queue_mgr,
            connection_manager=self.conn_mgr,
            state_store=self.state_store,
            metrics_collector=self.metrics,
        )
        new_file_source = FileSourceManager(
            config=self.config.sources["MSIS"],
            base_inflow_dir=self.inflow_dir,
            routing_engine=new_router,
            state_store=self.state_store,
            metrics_collector=self.metrics,
        )

        new_router.start()
        new_file_source.start()

        # Allow several polling cycles
        time.sleep(1.5)

        # Verify parser received NO additional envelopes for the same file
        self.assertEqual(len(self.parser.received_envelopes), 1, "Duplicate file was erroneously re-delivered!")

        new_file_source.stop()
        new_router.stop()


if __name__ == "__main__":
    unittest.main()
