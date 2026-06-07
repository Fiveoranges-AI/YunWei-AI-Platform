#!/usr/bin/env python3
"""Local preview harness for the dashboard (static/agents.html) as 邹总 sees it.

Serves the static dir and stubs /api/me + /api/agents with 邹总's tenant
(guangtian only, no proxied agents) so we can iterate on the guangtian-member
dashboard view without the full backend / prod auth. Dev-only; not shipped.

  python scripts/dev/dash_preview.py 8899
  → open http://localhost:8899/dashboard
"""
import json
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "services" / "platform-api" / "static"

ME = {
    "id": "u_zou_zong",
    "username": "zou_zong",
    "display_name": "邹总",
    "is_platform_admin": False,
    "enterprises": [
        {"id": "guangtian", "display_name": "宜兴光天耐火材料",
         "legal_name": "宜兴光天耐火材料有限公司", "role": "owner"},
    ],
}
AGENTS = {"agents": []}  # guangtian has no proxied agents → realCount 0 (matches prod)


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(STATIC), **k)

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/me":
            return self._json(ME)
        if self.path.split("?")[0] == "/api/agents":
            return self._json(AGENTS)
        if self.path.split("?")[0] in ("/dashboard", "/"):
            self.path = "/agents.html"
        return super().do_GET()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print(f"dash preview on http://localhost:{port}/dashboard")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
