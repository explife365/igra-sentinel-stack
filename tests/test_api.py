"""HTTP API integration tests (in-process server)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from sentinel_stack import api as api_mod
from sentinel_stack.api import SentinelHandler
from sentinel_stack.rate_limit import SlidingWindowLimiter


def _start_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), SentinelHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(base: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"error": raw}
        return int(err.code), parsed if isinstance(parsed, dict) else {"error": raw}


def test_health_and_status_endpoints() -> None:
    server, base = _start_server()
    try:
        health = _get(base, "/health")
        assert health["ok"] is True

        status = _get(base, "/v1/sentinel/status")
        assert status["ok"] is True
        assert status["not_consensus"] is True
        assert status["not_partnership"] is True
        assert status["not_mainnet_production"] is True
        galleon = status["networks"]["galleon_testnet"]
        mainnet = status["networks"]["igra_mainnet"]
        assert galleon["deploy_allowed"] is False
        assert galleon["chain_id"] == 38836
        assert mainnet["deploy_allowed"] is False
        assert mainnet["chain_id"] == 38833
        assert status["this_host"]["broadcast_shipped"] is False
        assert "walletconnect" not in [item["id"] for item in status["implemented"]]

        eco = _get(base, "/v1/igra/ecosystem")
        assert eco["not_partnership"] is True

        wc = _get(base, "/v1/dex/wallet/connect-config")
        assert wc["ok"] is True
        assert wc["network"]["chainIdDecimal"] == 38836
        assert wc["metadata"]["url"].endswith("/ui/dex")

        lp = _get(base, "/v1/liquidity/program")
        assert lp["ok"] is True
        assert lp["deploy_allowed"] is False
        assert lp["not_shipped_on_chain"] is True
        lend = _get(base, "/v1/lending/status")
        assert lend["ok"] is True and lend["not_shipped"] is True
        deriv = _get(base, "/v1/derivatives/status")
        assert deriv["ok"] is True and deriv["not_shipped"] is True
        assert deriv["deploy_allowed"] is False
        assert deriv["live_trading"] is False
        assert deriv["top_100"]["count"] == 80
        assert len(deriv.get("markets_catalog") or []) == 80

        trading = _get(base, "/v1/trading/console-config")
        assert trading["ok"] is True
        assert trading["live_trading"] is False
        assert len(trading.get("ohlc") or []) >= 50
        vol = _get(base, "/v1/trading/volume-rewards")
        assert vol["not_shipped"] is True
        assert vol["deploy_allowed"] is False
    finally:
        server.shutdown()


def test_security_headers() -> None:
    server, base = _start_server()
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=10) as resp:
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "DENY"
            assert resp.headers.get("Content-Security-Policy") == "frame-ancestors 'none'"
    finally:
        server.shutdown()


def _get_host(base: str, path: str, host: str) -> tuple[int, str]:
    req = urllib.request.Request(f"{base}{path}", headers={"Host": host})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return int(resp.status), resp.read().decode("utf-8")


def _get_headers(base: str, path: str, headers: dict[str, str]) -> tuple[int, str]:
    req = urllib.request.Request(f"{base}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return int(resp.status), resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return int(err.code), err.read().decode("utf-8", errors="replace")


def test_host_routes_three_surfaces(monkeypatch) -> None:
    monkeypatch.setattr(
        api_mod,
        "cex_rehearsal_status",
        lambda *_args, **_kwargs: {
            "ok": True,
            "custody_started": False,
            "owned_node_gate": {"status": "red"},
            "withdrawals": "not_shipped",
            "broadcast": "not_shipped",
            "orders": "not_shipped",
            "actions_enabled": False,
            "custody_listener": {"open": False, "port": 8787},
        },
    )
    server, base = _start_server()
    try:
        code, health = _get_host(base, "/health", "sentinel.tuce.app")
        body = json.loads(health)
        assert code == 200
        assert body["surface"] == "sentinel"
        assert body["not_partnership"] is True
        assert body["not_consensus"] is True
        assert body["not_mainnet_production"] is True

        _, dex_html = _get_host(base, "/", "dex.tuce.app")
        assert 'data-surface="dex"' in dex_html
        assert "38836" in dex_html
        assert "Swap broadcast is not shipped" in dex_html

        _, cex_html = _get_host(base, "/", "cex.tuce.app")
        assert 'data-surface="cex"' in cex_html
        assert "Custody not started" in cex_html
        assert "Owned-node gate: red" in cex_html
        assert "<form" not in cex_html.lower()

        _, sentinel_html = _get_host(base, "/", "sentinel.tuce.app")
        assert 'data-surface="sentinel"' in sentinel_html
        assert "https://dex.tuce.app" in sentinel_html
        assert "https://cex.tuce.app" in sentinel_html

        _, evil = _get_host(base, "/v1/dex/wallet/connect-config", "evil.example")
        cfg = json.loads(evil)
        assert "evil.example" not in cfg["public_origin"]
        assert cfg["broadcast_offered"] is False

        _, dex_cfg_raw = _get_host(base, "/v1/dex/wallet/connect-config", "dex.tuce.app")
        dex_cfg = json.loads(dex_cfg_raw)
        assert dex_cfg["public_origin"] == "https://dex.tuce.app"

        _, cex_raw = _get_host(base, "/v1/cex/status", "cex.tuce.app")
        cex = json.loads(cex_raw)
        assert cex["custody_started"] is False
        assert cex["owned_node_gate"]["status"] == "red"
        assert cex["custody_listener"]["open"] is False
    finally:
        server.shutdown()


def test_foreign_origin_rejected_on_metadata_paths() -> None:
    server, base = _start_server()
    try:
        for path in (
            "/v1/cex/status",
            "/v1/dex/wallet/connect-config",
        ):
            code, raw = _get_headers(
                base,
                path,
                {"Host": "127.0.0.1:8790", "Origin": "https://evil.example"},
            )
            assert code == 403
            body = json.loads(raw)
            assert body.get("error") == "foreign_origin_rejected"
            assert body.get("fail_closed") is True

        code, raw = _get_headers(
            base,
            "/v1/cex/status",
            {"Host": "127.0.0.1:8790"},
        )
        assert code == 200
        body = json.loads(raw)
        assert "evil.example" not in (body.get("public_origin") or "")
        assert body.get("public_origin") == "http://127.0.0.1:8790"
    finally:
        server.shutdown()


def test_post_rate_limit() -> None:
    original = api_mod.POST_LIMITER
    api_mod.POST_LIMITER = SlidingWindowLimiter(max_hits=2, window_sec=60)
    server, base = _start_server()
    try:
        path = "/v1/funding/bridge-verify"
        payload = {
            "transaction_intent_id": "97b4deadbeef",
            "source_chain_id": 10,
            "target_chain_id": 38836,
            "token_amount_tkas": 1,
            "l2_recipient": "0xb39f360Afc72908b89AA3413cF0e2Eb6D20B4B23",
        }
        code1, _ = _post(base, path, payload)
        code2, _ = _post(base, path, payload)
        code3, body3 = _post(base, path, payload)
        assert code1 == 200
        assert code2 == 200
        assert code3 == 429
        assert body3.get("error") == "rate_limited"
    finally:
        api_mod.POST_LIMITER = original
        server.shutdown()
