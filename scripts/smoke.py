#!/usr/bin/env python3
"""Smoke-test sentinel API (server must be running)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SENTINEL_API_BASE", "http://127.0.0.1:8790").rstrip("/")

CHECKS = (
    "/health",
    "/v1/sentinel/status",
    "/v1/igra/ecosystem",
    "/v1/networks",
    "/v1/dex/wallet/connect-config",
    "/v1/cex/status",
)

PUBLIC_HOSTS = ("sentinel.tuce.app", "dex.tuce.app", "cex.tuce.app")


def fetch(path: str, host: str | None = None) -> dict:
    headers = {"Accept": "application/json", "User-Agent": "igra-sentinel-smoke"}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(f"{BASE}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body if isinstance(body, dict) else {"raw": body}


def fetch_text(path: str, host: str) -> str:
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Host": host, "User-Agent": "igra-sentinel-smoke", "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> int:
    failed = 0

    def fail(msg: str) -> None:
        nonlocal failed
        print(f"FAIL {msg}")
        failed += 1

    for path in CHECKS:
        try:
            body = fetch(path)
            ok = body.get("ok", True)
            if path == "/health":
                flags = (
                    body.get("not_partnership"),
                    body.get("not_consensus"),
                    body.get("not_mainnet_production"),
                )
                if not all(flags):
                    fail(f"{path}: missing fail-closed banners")
                    continue
            if path == "/v1/sentinel/status":
                banners = (
                    body.get("not_partnership"),
                    body.get("not_consensus"),
                    body.get("not_mainnet_production"),
                )
                if not all(banners):
                    fail(f"{path}: missing fail-closed banners")
                    continue
                networks = body.get("networks") or {}
                mainnet = networks.get("igra_mainnet") or {}
                galleon = networks.get("galleon_testnet") or {}
                if mainnet.get("deploy_allowed") is not False:
                    fail(f"{path}: mainnet deploy_allowed is not false")
                    continue
                if mainnet.get("chain_id") != 38833:
                    fail(f"{path}: mainnet chain is not 38833")
                    continue
                if galleon.get("deploy_allowed") is not False:
                    fail(f"{path}: galleon deploy_allowed is not false")
                    continue
                if galleon.get("chain_id") != 38836:
                    fail(f"{path}: galleon chain is not 38836")
                    continue
                host_caps = body.get("this_host") or {}
                if host_caps.get("deploy_allowed") is not False:
                    fail(f"{path}: this host advertises deploy_allowed")
                    continue
                if host_caps.get("broadcast_shipped") is not False:
                    fail(f"{path}: this host advertises broadcast")
                    continue
                if host_caps.get("custody_started") is not False:
                    fail(f"{path}: this host advertises custody")
                    continue
                wc_on = host_caps.get("walletconnect_enabled") is True
                not_shipped = [item.get("id") for item in body.get("not_shipped") or []]
                if wc_on and "walletconnect" not in not_shipped:
                    fail(f"{path}: WalletConnect enabled but not documented in not_shipped")
                    continue
                g_probe = galleon.get("probe") or {}
                m_probe = mainnet.get("probe") or {}
                if g_probe.get("host_writes") is not False or m_probe.get("host_writes") is not False:
                    fail(f"{path}: a probe advertises host writes")
                    continue
            if path == "/v1/dex/wallet/connect-config":
                url = (body.get("metadata") or {}).get("url") or ""
                if "/ui/dex" not in url:
                    ok = False
                if body.get("broadcast_offered") is not False:
                    fail(f"{path}: broadcast_offered is not false")
                    continue
                wc = (body.get("connectors") or {}).get("walletconnect") or {}
                if wc.get("enabled") is True:
                    if not wc.get("project_id"):
                        fail(f"{path}: WalletConnect enabled without project_id")
                        continue
                    if body.get("broadcast_offered") is not False:
                        fail(f"{path}: WalletConnect on but broadcast_offered is not false")
                        continue
                elif wc.get("enabled") is not False or wc.get("project_id"):
                    fail(f"{path}: WalletConnect state inconsistent (disabled but project_id set?)")
                    continue
            if path == "/v1/cex/status":
                if body.get("custody_started") is not False:
                    fail(f"{path}: custody_started")
                    continue
                if body.get("actions_enabled") is not False:
                    fail(f"{path}: actions_enabled")
                    continue
                if (body.get("owned_node_gate") or {}).get("status") != "red":
                    fail(f"{path}: owned-node gate is not red")
                    continue
                if body.get("withdrawals") != "not_shipped" or body.get("broadcast") != "not_shipped":
                    fail(f"{path}: custody path is not marked not shipped")
                    continue
                if body.get("orders") != "not_shipped":
                    fail(f"{path}: orders are not marked not shipped")
                    continue
                listener = body.get("custody_listener") or {}
                if listener.get("open") is not False:
                    fail(f"{path}: custody listener is open on {listener.get('port')}")
                    continue
                tn10 = body.get("tn10") or {}
                if tn10.get("exposed_publicly") is not False or tn10.get("proxied") is not False:
                    fail(f"{path}: tn10 probe is not loopback-only")
                    continue
                gate = body.get("owned_node_gate") or {}
                if tn10.get("is_synced") is not True and gate.get("local_synced") is True:
                    fail(f"{path}: owned-node gate claims sync the probe did not")
                    continue
                if tn10.get("is_synced") is True and gate.get("local_synced") is not True:
                    fail(f"{path}: probe is synced but the gate ignored this host")
                    continue
            print(f"{'OK' if ok else 'WARN'} {path}")
            if not ok:
                failed += 1
        except Exception as err:  # noqa: BLE001
            fail(f"{path}: {err}")

    for host in PUBLIC_HOSTS:
        try:
            cfg = fetch("/v1/dex/wallet/connect-config", host)
            if cfg.get("public_origin") != f"https://{host}":
                fail(f"origin {host}: {cfg.get('public_origin')}")
            else:
                print(f"OK origin {host}")
        except Exception as err:  # noqa: BLE001
            fail(f"origin {host}: {err}")

    try:
        evil = fetch("/v1/dex/wallet/connect-config", "evil.example")
        if "evil.example" in (evil.get("public_origin") or ""):
            fail("foreign host was accepted as origin")
        else:
            print("OK foreign host rejected")
    except Exception as err:  # noqa: BLE001
        fail(f"foreign host: {err}")

    try:
        req = urllib.request.Request(
            f"{BASE}/v1/cex/status",
            headers={
                "Accept": "application/json",
                "User-Agent": "igra-sentinel-smoke",
                "Host": "127.0.0.1:8790",
                "Origin": "https://evil.example",
            },
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            fail(f"foreign Origin on loopback cex/status: HTTP {resp.status}")
    except urllib.error.HTTPError as err:
        if err.code != 403:
            fail(f"foreign Origin on loopback cex/status: HTTP {err.code}")
        else:
            print("OK foreign Origin rejected on cex/status")
    except Exception as err:  # noqa: BLE001
        fail(f"foreign Origin on cex/status: {err}")

    pages = {
        "sentinel.tuce.app": ("data-surface=\"sentinel\"", "https://dex.tuce.app", "https://cex.tuce.app", "Not an Igra partnership"),
        "dex.tuce.app": ("data-surface=\"dex\"", "38836", "galleon-testnet.igralabs.com", "Swap broadcast is not shipped"),
        "cex.tuce.app": ("data-surface=\"cex\"", "Custody not started", "Owned-node gate: red", "Withdrawals: not shipped"),
    }
    for host, needles in pages.items():
        try:
            html = fetch_text("/", host)
            missing = [needle for needle in needles if needle not in html]
            if missing:
                fail(f"page {host} missing {missing}")
            elif host == "cex.tuce.app" and "<form" in html.lower():
                fail("page cex contains a form")
            else:
                print(f"OK page {host}")
        except Exception as err:  # noqa: BLE001
            fail(f"page {host}: {err}")

    if failed:
        print(f"\n{failed} check(s) failed against {BASE}")
        return 1
    print(f"\nAll checks passed ({BASE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
