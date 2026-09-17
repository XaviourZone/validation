import argparse
import logging
import os
import signal
import threading
from pathlib import Path

from .api import make_server
from .config import load_config
from .service import ForwarderService


def project_root():
    value = os.environ.get("VALIDATION_HOME")
    if value:
        return Path(value).resolve()
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "Validation").is_dir():
            return parent
    return Path.cwd()


def main():
    parser = argparse.ArgumentParser(description="Validation Data Forwarder")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    root = project_root()
    config_path = Path(args.config) if args.config else root / "Validation/Data_Forwarder/config/forwarder.yaml"
    if not config_path.is_absolute():
        config_path = root / config_path

    cfg = load_config(config_path, root)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO), format="[%(asctime)s] [%(levelname)s] [DATA_FORWARDER] %(message)s")
    log = logging.getLogger("forwarder")
    service = ForwarderService(cfg, log)
    api = make_server(cfg.http_host, cfg.http_port, service)
    api_thread = threading.Thread(target=api.serve_forever, name="Forwarder-API", daemon=True)

    def shutdown(signum, frame):
        log.info("Signal %s received", signum)
        service.stop()
        api.shutdown()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    service.start()
    api_thread.start()
    log.info("Data Forwarder listening on %s:%s", cfg.http_host, cfg.http_port)
    try:
        while service.running:
            signal.pause()
    except (KeyboardInterrupt, SystemExit):
        shutdown(signal.SIGTERM, None)
    finally:
        api.server_close()


if __name__ == "__main__":
    main()
