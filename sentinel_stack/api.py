"""Igra Sentinel HTTP API."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sentinel_stack.env import load_env
from sentinel_stack.evm_validator import validate_safety_payload
from sentinel_stack.igra_ecosystem import igra_ecosystem_catalog
from sentinel_stack.katbridge import validate_bridge_payload
from sentinel_stack.networks import networks_catalog, wallet_connect_config
from sentinel_stack.status import sentinel_status

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "ui"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


class SentinelHandler(BaseHTTPRequestHandler):
    server_version = "igra-sentinel/0.1"

    def _json(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return body if isinstance(body, dict) else {}

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            self._json(404, {"ok": False, "error": "not found", "path": str(path)})
            return
        data = path.read_bytes()
        mime = MIME.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            self._json(200, {"ok": True, "service": "igra-sentinel-stack"})
            return
        if path == "/v1/sentinel/status":
            self._json(200, sentinel_status())
            return
        if path == "/v1/igra/ecosystem":
            self._json(200, igra_ecosystem_catalog())
            return
        if path == "/v1/networks":
            self._json(200, networks_catalog())
            return
        if path == "/v1/dex/wallet/network":
            cfg = wallet_connect_config()
            self._json(200, {"ok": True, "network": cfg["network"], "not_mainnet": True})
            return
        if path == "/v1/dex/wallet/connect-config":
            self._json(200, wallet_connect_config())
            return

        if path in ("/", "/ui"):
            self._serve_file(UI_ROOT / "index.html")
            return
        if path == "/ui/dex":
            self._serve_file(UI_ROOT / "dex" / "index.html")
            return
        if path.startswith("/ui/"):
            rel = path.removeprefix("/ui/").lstrip("/")
            if rel and ".." not in rel:
                self._serve_file(UI_ROOT / rel.replace("/", os.sep))
                return

        self._json(404, {"ok": False, "error": "not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_json()

        if path == "/v1/evm/safety-verify":
            try:
                self._json(200, validate_safety_payload(body))
            except Exception as err:  # noqa: BLE001
                self._json(400, {"ok": False, "error": str(err)})
            return
        if path == "/v1/funding/bridge-verify":
            self._json(200, validate_bridge_payload(body))
            return

        self._json(404, {"ok": False, "error": "not found", "path": path})

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def run_server(host: str | None = None, port: int | None = None) -> None:
    load_env()
    bind_host = host or os.environ.get("SENTINEL_API_HOST", "127.0.0.1")
    bind_port = port or int(os.environ.get("SENTINEL_API_PORT", "8790"))
    server = ThreadingHTTPServer((bind_host, bind_port), SentinelHandler)
    print(f"igra-sentinel listening http://{bind_host}:{bind_port}")
    print(f"  dashboard  http://{bind_host}:{bind_port}/ui")
    print(f"  status     http://{bind_host}:{bind_port}/v1/sentinel/status")
    server.serve_forever()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Igra Sentinel API")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
