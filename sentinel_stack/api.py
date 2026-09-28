"""Igra Sentinel HTTP API."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sentinel_stack.cex_status import cex_rehearsal_status
from sentinel_stack.env import load_env
from sentinel_stack.evm_validator import validate_safety_payload
from sentinel_stack.igra_ecosystem import igra_ecosystem_catalog
from sentinel_stack.katbridge import validate_bridge_payload
from sentinel_stack.networks import (
    foreign_origin_header,
    networks_catalog,
    surface_for_host,
    wallet_connect_config,
)
from sentinel_stack.rate_limit import POST_LIMITER, client_key
from sentinel_stack.integrator_readonly import READONLY_GET_PATHS, get_readonly
from sentinel_stack.status import sentinel_status

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "ui"

ORIGIN_METADATA_PATHS = frozenset(
    {
        "/v1/dex/wallet/connect-config",
        "/v1/dex/wallet/network",
        "/v1/networks",
        "/v1/cex/status",
    }
)

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

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store")

    def _json(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers()
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

    def _reject_foreign_origin(self) -> bool:
        if foreign_origin_header(self.headers.get("Origin")):
            self._json(
                403,
                {
                    "ok": False,
                    "error": "foreign_origin_rejected",
                    "fail_closed": True,
                    "not_partnership": True,
                },
            )
            return True
        return False

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            self._json(404, {"ok": False, "error": "not found", "path": str(path)})
            return
        data = path.read_bytes()
        mime = MIME.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _surface_page(self, surface: str) -> Path:
        if surface == "dex":
            return UI_ROOT / "dex" / "index.html"
        if surface == "cex":
            return UI_ROOT / "cex" / "index.html"
        return UI_ROOT / "index.html"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        surface = surface_for_host(host)

        if path in ORIGIN_METADATA_PATHS and self._reject_foreign_origin():
            return

        if path == "/health":
            self._json(
                200,
                {
                    "ok": True,
                    "service": "igra-sentinel-stack",
                    "surface": surface,
                    "not_partnership": True,
                    "not_consensus": True,
                    "not_mainnet_production": True,
                },
            )
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
        if path == "/v1/cex/status":
            self._json(200, cex_rehearsal_status(host, origin))
            return
        if path == "/v1/dex/wallet/network":
            cfg = wallet_connect_config(host, origin)
            self._json(200, {"ok": True, "network": cfg["network"], "not_mainnet": True})
            return
        if path == "/v1/dex/wallet/connect-config":
            self._json(200, wallet_connect_config(host, origin))
            return
        if path in READONLY_GET_PATHS:
            qs = parse_qs(parsed.query)
            self._json(200, get_readonly(path, qs))
            return

        if path in ("/", "/ui"):
            self._serve_file(self._surface_page(surface))
            return
        if path == "/ui/dex":
            self._serve_file(UI_ROOT / "dex" / "index.html")
            return
        if path == "/ui/cex":
            self._serve_file(UI_ROOT / "cex" / "index.html")
            return
        if path.startswith("/ui/"):
            rel = path.removeprefix("/ui/").lstrip("/")
            if rel and ".." not in rel and "\\" not in rel:
                candidate = (UI_ROOT / rel.replace("/", os.sep)).resolve()
                root = UI_ROOT.resolve()
                if candidate.is_relative_to(root) and candidate.is_file():
                    self._serve_file(candidate)
                    return

        self._json(404, {"ok": False, "error": "not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_json()
        gated = path in ("/v1/evm/safety-verify", "/v1/funding/bridge-verify")
        if gated and not POST_LIMITER.allow(client_key(self)):
            self._json(
                429,
                {
                    "ok": False,
                    "error": "rate_limited",
                    "fail_closed": True,
                    "path": path,
                },
            )
            return

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
