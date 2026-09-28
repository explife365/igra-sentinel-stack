"""Read-only integrator LP / lending / derivatives for dex.tuce.app.

Tries INTEGRATOR_REACH_URL (server-side) when host02 can reach host03 :8788.
Otherwise serves the same rehearsal JSON locally (fail-closed flags preserved).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

READONLY_GET_PATHS = frozenset(
    {
        "/v1/liquidity/program",
        "/v1/lending/status",
        "/v1/derivatives/status",
        "/v1/trading/console-config",
        "/v1/trading/volume-rewards",
        "/v1/trading/financing",
        "/v1/trading/leaderboard",
        "/v1/trading/copy-trading/status",
        "/v1/trading/automation-policy",
        "/v1/trading/order-book",
        "/v1/trading/ticker",
        "/v1/trading/order-types",
        "/v1/trading/exchange-features",
        "/v1/trading/demo-wallets",
    }
)


def _reach_base() -> str:
    for name in ("INTEGRATOR_REACH_URL", "INTEGRATOR_DEX_REACH_URL"):
        value = (os.environ.get(name) or "").strip().rstrip("/")
        if value:
            return value
    return ""


def _proxy_fetch(path: str, timeout_s: float = 2.5) -> dict[str, Any] | None:
    base = _reach_base()
    if not base:
        return None
    url = f"{base}{path}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if int(resp.status) != 200:
                return None
            payload = json.loads(resp.read(131_072).decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return None
    out = dict(payload)
    out["fetched_via"] = "integrator_reach"
    return out


def _local(path: str, qs: dict[str, list[str]] | None = None) -> dict[str, Any]:
    from sentinel_stack.liquidity_program import (
        derivatives_status,
        lending_status,
        program_status,
    )
    from sentinel_stack.trading_console import (
        automation_policy,
        console_config,
        copy_trading_status,
        demo_wallets,
        exchange_features,
        financing_rate,
        leaderboard,
        order_book,
        order_types_policy,
        ticker_24h,
        volume_tiers,
    )

    query = qs or {}
    symbol = (query.get("symbol") or [None])[0]
    wallet = (query.get("wallet") or query.get("trader") or [None])[0]
    limit_raw = (query.get("limit") or ["20"])[0]
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 20

    if path == "/v1/liquidity/program":
        body = program_status()
    elif path == "/v1/lending/status":
        body = lending_status()
    elif path == "/v1/derivatives/status":
        body = derivatives_status()
    elif path == "/v1/trading/console-config":
        body = console_config(symbol)
    elif path == "/v1/trading/volume-rewards":
        body = volume_tiers(wallet)
    elif path == "/v1/trading/financing":
        body = financing_rate()
    elif path == "/v1/trading/leaderboard":
        body = leaderboard(limit)
    elif path == "/v1/trading/copy-trading/status":
        body = copy_trading_status(wallet)
    elif path == "/v1/trading/automation-policy":
        body = automation_policy()
    elif path == "/v1/trading/order-book":
        body = order_book(symbol)
    elif path == "/v1/trading/ticker":
        body = ticker_24h(symbol)
    elif path == "/v1/trading/order-types":
        body = order_types_policy()
    elif path == "/v1/trading/exchange-features":
        body = exchange_features()
    elif path == "/v1/trading/demo-wallets":
        body = demo_wallets()
    else:
        return {"ok": False, "error": "unknown path", "path": path}
    out = dict(body)
    out["fetched_via"] = "sentinel_local_rehearsal"
    return out


def get_readonly(path: str, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    qs = query or {}
    extra = ""
    if path in ("/v1/trading/console-config", "/v1/trading/order-book", "/v1/trading/ticker") and qs.get(
        "symbol"
    ):
        extra = f"?symbol={qs['symbol'][0]}"
    elif path in ("/v1/trading/volume-rewards", "/v1/trading/copy-trading/status"):
        w = (qs.get("wallet") or qs.get("trader") or [None])[0]
        if w:
            extra = f"?wallet={w}"
    elif path == "/v1/trading/leaderboard" and qs.get("limit"):
        extra = f"?limit={qs['limit'][0]}"
    proxied = _proxy_fetch(f"{path}{extra}")
    if proxied is not None:
        return proxied
    return _local(path, qs)
