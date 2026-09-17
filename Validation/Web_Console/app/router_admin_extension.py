"""Web Console extension for Router source browsing and parser mappings."""

import json
import os
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from Validation.Data_Parser.app.pipeline.mapping_manager import ParserMappingManager, default_mapping_for


ALLOWED_FILE_PATTERNS = ["*.csv", "*.xml", "*.json", "*.txt", "*.nmea", "*.log", "*"]


def install_router_admin_extension(handler_class, workspace_root, config_manager, logger):
    if getattr(handler_class, "_router_admin_extension_installed", False):
        return
    handler_class._router_admin_extension_installed = True
    handler_class.router_admin_workspace_root = Path(workspace_root)
    handler_class.router_admin_config_manager = config_manager
    handler_class.router_admin_logger = logger
    handler_class.router_mapping_manager = ParserMappingManager(
        Path(workspace_root) / "Validation" / "Data_Parser" / "config" / "parser_mappings.yaml"
    )

    original_get = handler_class.do_GET
    original_post = handler_class.do_POST
    original_dashboard = handler_class._serve_dashboard

    def do_get(self):
        path = urlparse(self.path).path
        if path == "/api/router/filesystem/browse":
            self._router_browse(); return
        if path == "/api/router/filesystem/patterns":
            self._json_response({"patterns": ALLOWED_FILE_PATTERNS}); return
        if path == "/api/parser/mapping/fields":
            self._json_response({"fields": self.router_mapping_manager.fields()}); return
        if path == "/api/parser/mapping/parsers":
            names = self.router_mapping_manager.parser_names()
            configured = list(self.router_admin_config_manager.get_parser_destinations().keys())
            for name in configured:
                if name not in names:
                    names.append(name)
            self._json_response({"parsers": names}); return
        if path == "/api/parser/mapping":
            query = parse_qs(urlparse(self.path).query)
            name = (query.get("parser") or [""])[0]
            if not name:
                self._json_response({"error": "parser query parameter is required"}, status=HTTPStatus.BAD_REQUEST); return
            mapping = self.router_mapping_manager.get(name)
            if not mapping.get("fields") or all(not v for v in mapping["fields"].values()):
                mapping = default_mapping_for(name)
            self._json_response({"parser": name, "mapping": mapping}); return
        if path == "/api/parser/ais-state":
            query = parse_qs(urlparse(self.path).query)
            try:
                mmsi = int((query.get("mmsi") or [""])[0])
                from Validation.Data_Parser.app.pipeline.ais_state import AISStateDB
                db = AISStateDB()
                self._json_response({"mmsi": mmsi, "state": db.get(mmsi), "recent_messages": db.recent_messages(mmsi)})
                db.close()
            except Exception as exc:
                self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        return original_get(self)

    def do_post(self):
        path = urlparse(self.path).path
        if path == "/api/parser/mapping/save":
            self._router_save_mapping(); return
        return original_post(self)

    def serve_dashboard(self):
        if not self.template_path.exists():
            return original_dashboard(self)
        try:
            content = self.template_path.read_text(encoding="utf-8")
            script = '<script src="/static/js/router_admin.js"></script>'
            if script not in content:
                content = content.replace("</body>", f"{script}\n</body>")
            body = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            self._error_response(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading dashboard: {exc}")

    def _router_browse(self):
        query = parse_qs(urlparse(self.path).query)
        raw = (query.get("path") or [""])[0]
        path = Path(raw).expanduser() if raw else Path("/")
        try:
            path = path.resolve()
            if not path.exists() or not path.is_dir():
                self._json_response({"error": f"Directory does not exist: {path}"}, status=HTTPStatus.NOT_FOUND); return
            entries = []
            for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if child.is_dir() and not child.name.startswith("."):
                    try:
                        readable = os.access(child, os.R_OK | os.X_OK)
                    except OSError:
                        readable = False
                    entries.append({"name": child.name, "path": str(child), "readable": readable})
            parent = str(path.parent) if path.parent != path else None
            self._json_response({"path": str(path), "parent": parent, "entries": entries})
        except Exception as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _router_save_mapping(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            name = str(body.get("parser") or "").strip()
            mapping = body.get("mapping") or {}
            saved = self.router_mapping_manager.save(name, mapping)
            self._json_response({"success": True, "parser": name, "mapping": saved})
        except Exception as exc:
            self._json_response({"success": False, "error": str(exc)}, status=HTTPStatus.UNPROCESSABLE_ENTITY)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post
    handler_class._serve_dashboard = serve_dashboard
    handler_class._router_browse = _router_browse
    handler_class._router_save_mapping = _router_save_mapping
