import hashlib
import json
import logging
import shutil
import threading
import time
from pathlib import Path

from .config import ForwarderConfig
from .state import DeliveryState
from .transport import DeliveryError, transport_for


class ForwarderService:
    def __init__(self, config: ForwarderConfig, logger=None):
        self.config = config
        self.log = logger or logging.getLogger("forwarder")
        self.state = DeliveryState(config.spool.state_db)
        self.running = False
        self._thread = None
        self._lock = threading.RLock()
        for path in (config.spool.input_dir, config.spool.archive_dir, config.spool.failed_dir):
            path.mkdir(parents=True, exist_ok=True)

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, name="ForwarderWorker", daemon=True)
        self._thread.start()
        self.log.info("Data Forwarder started")

    def stop(self):
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self.log.info("Data Forwarder stopped")

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _output_id(path: Path, sha256: str) -> str:
        # Output metadata is optional. Filename + content hash is deterministic.
        return f"{path.stem}:{sha256[:16]}"

    def _loop(self):
        while self.running:
            try:
                self.process_once()
            except Exception:
                self.log.exception("Unhandled Forwarder loop error")
            time.sleep(max(0.1, self.config.spool.poll_interval_seconds))

    def process_once(self):
        files = sorted(self.config.spool.input_dir.glob("*.xml"))
        if not files:
            return
        enabled = [d for d in self.config.destinations.values() if d.enabled]
        if not enabled:
            self.log.warning("No enabled Forwarder destinations; leaving XML files pending")
            return

        for path in files:
            if not self.running:
                break
            self._process_file(path, enabled)

    def _process_file(self, path: Path, destinations):
        sha = self._sha256(path)
        output_id = self._output_id(path, sha)
        all_delivered = True

        for dest in destinations:
            current = self.state.get(output_id, dest.name)
            if current and current["state"] == "DELIVERED" and current["sha256"] == sha:
                continue

            self.state.ensure(output_id, dest.name, sha, path.name)
            ok = self._deliver_with_retry(path, output_id, dest)
            all_delivered = all_delivered and ok

        if all_delivered:
            archive_target = self.config.spool.archive_dir / path.name
            if archive_target.exists():
                archive_target = self.config.spool.archive_dir / f"{path.stem}_{sha[:12]}{path.suffix}"
            try:
                path.replace(archive_target)
            except OSError as exc:
                self.log.error("Delivered but could not archive %s: %s", path, exc)

    def _deliver_with_retry(self, path, output_id, destination):
        transport = transport_for(destination)
        delay = self.config.retry.initial_delay_seconds
        last_error = None
        for attempt in range(1, self.config.retry.max_attempts + 1):
            self.state.mark(output_id, destination.name, "TRANSFERRING", attempts=attempt)
            try:
                transport.deliver(path, destination)
                self.state.mark(output_id, destination.name, "DELIVERED", attempts=attempt)
                self.log.info("Delivered %s to %s", path.name, destination.name)
                return True
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.config.retry.max_attempts:
                    self.state.mark(output_id, destination.name, "RETRYING", attempts=attempt, error=last_error)
                    time.sleep(delay)
                    delay = min(self.config.retry.max_delay_seconds, delay * self.config.retry.multiplier)
                else:
                    self.state.mark(output_id, destination.name, "FAILED", attempts=attempt, error=last_error)
                    self.log.error("Delivery failed for %s to %s: %s", path.name, destination.name, last_error)
        return False

    def metrics(self):
        counts = self.state.counts()
        pending = len(list(self.config.spool.input_dir.glob("*.xml")))
        return {"pending_files": pending, "states": counts, "destinations": list(self.config.destinations)}
