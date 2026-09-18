"""HTTP API integration tests (in-process server)."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from sentinel_stack.api import SentinelHandler


def _start_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), SentinelHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_health_and_status_endpoints() -> None:
    server, base = _start_server()
    try:
        health = _get(base, "/health")
        assert health["ok"] is True

        status = _get(base, "/v1/sentinel/status")
        assert status["ok"] is True
        assert status["not_consensus"] is True

        eco = _get(base, "/v1/igra/ecosystem")
        assert eco["not_partnership"] is True

        wc = _get(base, "/v1/dex/wallet/connect-config")
        assert wc["ok"] is True
        assert wc["network"]["chainIdDecimal"] == 38836
    finally:
        server.shutdown()
