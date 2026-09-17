"""Web Console extension for database source configuration.

PANS is a live XML feed. This extension lets an operator select its input
folder and safely persists the setting in Database/config/database.yaml.
No database credentials are involved because PANS is SQLite.
"""

import os
import tempfile
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml


DATABASE_CONFIG = "Validation/Database/config/database.yaml"
PANS_SERVICE = "validation-pans-importer.service"


def _atomic_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def install_database_admin_extension(handler_class, workspace_root, service_controller, logger):
    if getattr(handler_class, "_database_admin_extension_installed", False):
        return
    handler_class._database_admin_extension_installed = True
    handler_class.database_admin_workspace_root = Path(workspace_root)
    handler_class.database_admin_config_path = handler_class.database_admin_workspace_root / DATABASE_CONFIG
    handler_class.database_admin_service_controller = service_controller
    handler_class.database_admin_logger = logger

    original_get = handler_class.do_GET
    original_post = handler_class.do_POST
    original_dashboard = handler_class._serve_dashboard

    def do_get(self):
        path = urlparse(self.path).path
        if path == "/api/database/filesystem/browse":
            self._database_browse()
            return
        if path == "/api/database/pans/config":
            self._database_pans_config()
            return
        return original_get(self)

    def do_post(self):
        path = urlparse(self.path).path
        if path == "/api/database/pans/config":
            self._database_save_pans()
            return
        return original_post(self)

    def serve_dashboard(self):
        if not self.template_path.exists():
            return original_dashboard(self)
        try:
            content = self.template_path.read_text(encoding="utf-8")
            scripts = (
                '<script src="/static/js/forwarder.js?v=20260918"></script>\n'
                '<script src="/static/js/router_admin.js?v=20260918"></script>\n'
                '<script src="/static/js/database_admin.js?v=20260918"></script>\n'
                '<script src="/static/js/console_polish.js?v=20260918"></script>'
            )
            # This is the final dashboard wrapper. Load the complete UI set
            # once, with cache-busting, regardless of wrapper installation order.
            for src in (
                "/static/js/forwarder.js",
                "/static/js/router_admin.js",
                "/static/js/database_admin.js",
                "/static/js/console_polish.js",
            ):
                content = content.replace(
                    content[content.find("<script", content.find(src) - 20):content.find("</script>", content.find(src)) + 9]
                    if content.find(src) >= 0 and content.find("<script", content.find(src) - 20) >= 0
                    else "__NO_MATCH__",
                    "",
                )
            content = content.replace("</body>", f"{scripts}\n</body>")
            body = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            self._error_response(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading dashboard: {exc}")

    def _browse_roots(self):
        if os.name == "nt":
            roots = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                root = Path(f"{letter}:\\")
                if root.exists():
                    roots.append(root)
            return roots or [Path.cwd().anchor and Path(Path.cwd().anchor) or Path.cwd()]
        return [Path("/")]

    def _database_browse(self):
        query = parse_qs(urlparse(self.path).query)
        raw = (query.get("path") or [""])[0].strip()
        try:
            if raw:
                path = Path(raw).expanduser().resolve()
            else:
                roots = self._browse_roots()
                self._json_response({
                    "roots": [{"name": str(p), "path": str(p), "readable": os.access(p, os.R_OK)} for p in roots]
                })
                return
            if not path.exists() or not path.is_dir():
                self._json_response({"error": f"Directory does not exist: {path}"}, status=HTTPStatus.NOT_FOUND)
                return
            entries = []
            for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                try:
                    readable = os.access(child, os.R_OK | os.X_OK)
                except OSError:
                    readable = False
                entries.append({"name": child.name, "path": str(child), "readable": readable})
            self._json_response({
                "path": str(path),
                "parent": str(path.parent) if path.parent != path else None,
                "entries": entries,
            })
        except Exception as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _read_database_config(self):
        if not self.database_admin_config_path.exists():
            return {}
        return yaml.safe_load(self.database_admin_config_path.read_text(encoding="utf-8")) or {}

    def _database_pans_config(self):
        cfg = self._read_database_config()
        pans = (cfg.get("imports", {}) or {}).get("pans", {}) or {}
        self._json_response({
            "input_dir": str(pans.get("input_dir", "Validation/Database/PANS/RAW_DATA")),
            "poll_interval_seconds": float(pans.get("poll_interval_seconds", 2.0)),
            "stability_seconds": float(pans.get("stability_seconds", 1.0)),
            "service": PANS_SERVICE,
        })

    def _database_save_pans(self):
        import json
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            folder = str(body.get("input_dir", "")).strip()
            if not folder:
                raise ValueError("PANS XML source folder is required")
            path = Path(folder).expanduser().resolve()
            if not path.exists() or not path.is_dir():
                raise ValueError(f"PANS XML source folder does not exist: {path}")
            if not os.access(path, os.R_OK | os.X_OK):
                raise ValueError(f"PANS XML source folder is not readable: {path}")

            cfg = self._read_database_config()
            imports = cfg.setdefault("imports", {})
            pans = imports.setdefault("pans", {})
            # Store an absolute operator-selected path. Runtime remains fully
            # portable because Path is used by the importer on both Windows/Linux.
            pans["input_dir"] = str(path)
            pans.setdefault("poll_interval_seconds", 2.0)
            pans.setdefault("stability_seconds", 1.0)
            pans.setdefault("batch_size", 500)
            _atomic_yaml(self.database_admin_config_path, cfg)

            restart = None
            try:
                restart = self.database_admin_service_controller.restart_service(PANS_SERVICE)
            except Exception as exc:
                restart = {"success": False, "message": f"Configuration saved; PANS restart pending: {exc}"}
            self._json_response({"success": True, "input_dir": str(path), "restart": restart})
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, status=HTTPStatus.UNPROCESSABLE_ENTITY)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._serve_dashboard = serve_dashboard
    handler_class._database_browse = _database_browse
    handler_class._database_pans_config = _database_pans_config
    handler_class._database_save_pans = _database_save_pans
