"""Web Console integration for Data Forwarder destinations.

The production destination is an SFTP/SSH data-diode endpoint. The browser
never receives the password; it can only set/replace it locally.
"""

import json
import os
import re
import tempfile
import urllib.request
from http import HTTPStatus
from pathlib import Path

import yaml


_SECRET_FILE = "Validation/Data_Forwarder/state/forwarder_secrets.json"
_CONFIG_FILE = "Validation/Data_Forwarder/config/forwarder.yaml"
_API_URL = "http://127.0.0.1:8082"


def _json_request(url, method="GET", payload=None, timeout=2.5):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _atomic_write(path: Path, content: str, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        if mode is not None and os.name != "nt":
            os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def install_forwarder_web_extension(handler_class, workspace_root, service_controller, service_name, logger):
    if getattr(handler_class, "_forwarder_extension_installed", False):
        return
    handler_class._forwarder_extension_installed = True
    handler_class.forwarder_workspace_root = Path(workspace_root)
    handler_class.forwarder_config_path = handler_class.forwarder_workspace_root / _CONFIG_FILE
    handler_class.forwarder_secret_path = handler_class.forwarder_workspace_root / _SECRET_FILE
    handler_class.forwarder_service_controller = service_controller
    handler_class.forwarder_service_name = service_name
    handler_class.forwarder_logger = logger

    original_get = handler_class.do_GET
    original_post = handler_class.do_POST

    def do_get(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        if path == "/api/forwarder/status":
            self._forwarder_status()
            return
        if path == "/api/forwarder/metrics":
            self._forwarder_proxy_get("/metrics")
            return
        if path == "/api/forwarder/destinations":
            self._forwarder_destinations()
            return
        if path == "/api/forwarder/deliveries":
            self._forwarder_proxy_get("/deliveries")
            return
        return original_get(self)

    def do_post(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        if path.startswith("/api/forwarder/"):
            self._forwarder_post(path)
            return
        return original_post(self)

    def _forwarder_config(self):
        if not self.forwarder_config_path.exists():
            return {"server": {"http_host": "127.0.0.1", "http_port": 8082}, "destinations": {}}
        return yaml.safe_load(self.forwarder_config_path.read_text(encoding="utf-8")) or {}

    def _forwarder_secrets(self):
        if not self.forwarder_secret_path.exists():
            return {}
        try:
            data = json.loads(self.forwarder_secret_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_forwarder_files(self, config, secrets):
        self.forwarder_config_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(
            self.forwarder_config_path,
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        )
        _atomic_write(
            self.forwarder_secret_path,
            json.dumps(secrets, indent=2) + "\n",
            0o600,
        )

    def _forwarder_destinations(self):
        cfg, secrets = self._forwarder_config(), self._forwarder_secrets()
        result = []
        for name, value in (cfg.get("destinations", {}) or {}).items():
            value = value or {}
            result.append({
                "name": name,
                "enabled": bool(value.get("enabled", False)),
                "protocol": "sftp",
                "host": str(value.get("host", "")),
                "port": int(value.get("port", 22)),
                "remote_path": str(value.get("remote_path", "")),
                "username": str(value.get("username", "")),
                "password_configured": bool(secrets.get(name)),
                "private_key_file": str(value.get("private_key_file", "")),
                "connect_timeout_seconds": int(value.get("connect_timeout_seconds", 10)),
                "verify_remote_size": bool(value.get("verify_remote_size", True)),
            })
        self._json_response({"destinations": result})

    def _forwarder_status(self):
        svc = self.forwarder_service_controller.get_service_status(self.forwarder_service_name)
        try:
            health = _json_request(f"{_API_URL}/health")
            reachable = True
        except Exception:
            health = {"status": "OFFLINE", "running": False}
            reachable = False
        status = "RUNNING" if reachable and health.get("running", True) else svc.get("status", "UNKNOWN")
        self._json_response({
            "service": "validation-data-forwarder",
            "status": status,
            "reachable": reachable,
            "service_info": svc,
            "health": health,
        })

    def _forwarder_proxy_get(self, endpoint):
        try:
            self._json_response(_json_request(f"{_API_URL}{endpoint}"))
        except Exception as exc:
            self._json_response({"reachable": False, "error": str(exc)}, status=HTTPStatus.SERVICE_UNAVAILABLE)

    def _forwarder_post(self, path):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            self._error_response(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
            return

        if path == "/api/forwarder/start":
            self._json_response(self.forwarder_service_controller.start_service(self.forwarder_service_name))
            return
        if path == "/api/forwarder/stop":
            self._json_response(self.forwarder_service_controller.stop_service(self.forwarder_service_name))
            return
        if path == "/api/forwarder/restart":
            self._json_response(self.forwarder_service_controller.restart_service(self.forwarder_service_name))
            return
        if path == "/api/forwarder/reload":
            try:
                result = _json_request(f"{_API_URL}/config/reload", method="POST", payload={}, timeout=5)
                self._json_response(result)
            except Exception as exc:
                self._json_response({
                    "success": True,
                    "reload_required": True,
                    "message": f"Configuration saved; Forwarder reload pending ({exc})",
                })
            return
        if path == "/api/forwarder/test":
            try:
                result = _json_request(
                    f"{_API_URL}/config/destinations/test",
                    method="POST",
                    payload={"name": body.get("name", "")},
                    timeout=5,
                )
                self._json_response(result)
            except Exception as exc:
                self._json_response({"success": False, "error": str(exc)}, status=HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if path == "/api/forwarder/destinations/save":
            self._save_destination(body)
            return

        match = re.match(r"^/api/forwarder/destinations/([^/]+)/(delete|enable|disable)$", path)
        if match:
            self._modify_destination(match.group(1), match.group(2))
            return

        self._error_response(HTTPStatus.NOT_FOUND, "Forwarder endpoint not found")

    def _save_destination(self, body):
        name = str(body.get("name", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            self._error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid destination name")
            return

        cfg = self._forwarder_config()
        destinations = cfg.setdefault("destinations", {})
        existing = destinations.get(name) or {}

        host = str(body.get("host", existing.get("host", ""))).strip()
        remote_path = str(body.get("remote_path", existing.get("remote_path", ""))).strip()
        username = str(body.get("username", existing.get("username", ""))).strip()
        key_file = str(body.get("private_key_file", existing.get("private_key_file", ""))).strip()
        enabled = bool(body.get("enabled", existing.get("enabled", False)))

        try:
            port = int(body.get("port", existing.get("port", 22)))
            timeout = int(body.get("connect_timeout_seconds", existing.get("connect_timeout_seconds", 10)))
        except (TypeError, ValueError):
            self._error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "SSH port and timeout must be numeric")
            return

        if not host or not remote_path or not username:
            self._error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "Host, remote folder and SSH username are required")
            return
        if not 1 <= port <= 65535:
            self._error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "SSH port must be between 1 and 65535")
            return
        if timeout < 1:
            self._error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "Connection timeout must be at least 1 second")
            return

        secrets = self._forwarder_secrets()
        password = body.get("password")
        if isinstance(password, str) and password:
            secrets[name] = password

        if name not in secrets and not key_file:
            self._json_response({
                "success": False,
                "password_required": True,
                "error": "SSH password is not configured. Enter the Data Diode password before saving.",
            }, status=HTTPStatus.UNPROCESSABLE_ENTITY)
            return

        destinations[name] = {
            "enabled": enabled,
            "protocol": "sftp",
            "host": host,
            "port": port,
            "remote_path": remote_path,
            "username": username,
            "private_key_file": key_file,
            "connect_timeout_seconds": timeout,
            "verify_remote_size": True,
        }

        self._write_forwarder_files(cfg, secrets)

        try:
            result = _json_request(f"{_API_URL}/config/reload", method="POST", payload={}, timeout=5)
        except Exception as exc:
            result = {"success": True, "reload_required": True, "message": f"Saved; reload pending ({exc})"}

        self._json_response({
            "success": True,
            "destination": name,
            "password_configured": bool(secrets.get(name)) or bool(key_file),
            "reload": result,
        })

    def _modify_destination(self, name, action):
        cfg = self._forwarder_config()
        destinations = cfg.setdefault("destinations", {})
        if name not in destinations:
            self._error_response(HTTPStatus.NOT_FOUND, f"Destination '{name}' not found")
            return

        secrets = self._forwarder_secrets()
        if action == "delete":
            destinations.pop(name, None)
            secrets.pop(name, None)
        else:
            destinations[name]["enabled"] = action == "enable"

        self._write_forwarder_files(cfg, secrets)
        try:
            result = _json_request(f"{_API_URL}/config/reload", method="POST", payload={}, timeout=5)
        except Exception as exc:
            result = {"success": True, "reload_required": True, "message": f"Saved; reload pending ({exc})"}
        self._json_response(result)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._forwarder_config = _forwarder_config
    handler_class._forwarder_secrets = _forwarder_secrets
    handler_class._write_forwarder_files = _write_forwarder_files
    handler_class._forwarder_destinations = _forwarder_destinations
    handler_class._forwarder_status = _forwarder_status
    handler_class._forwarder_proxy_get = _forwarder_proxy_get
    handler_class._forwarder_post = _forwarder_post
    handler_class._save_destination = _save_destination
    handler_class._modify_destination = _modify_destination
