import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_server(host, port, service):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload, code=200):
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send({"status": "READY", "service": "data-forwarder"})
            elif self.path == "/metrics":
                self._send(service.metrics())
            elif self.path == "/deliveries":
                self._send({"deliveries": service.state.recent()})
            else:
                self._send({"error": "not found"}, 404)

        def log_message(self, fmt, *args):
            return

    return ThreadingHTTPServer((host, port), Handler)
