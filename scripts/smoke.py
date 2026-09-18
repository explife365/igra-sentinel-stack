#!/usr/bin/env python3
"""Smoke-test local sentinel API (server must be running)."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("SENTINEL_API_BASE", "http://127.0.0.1:8790").rstrip("/")

CHECKS = (
    "/health",
    "/v1/sentinel/status",
    "/v1/igra/ecosystem",
    "/v1/networks",
    "/v1/dex/wallet/connect-config",
)


def fetch(path: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Accept": "application/json", "User-Agent": "igra-sentinel-smoke"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body if isinstance(body, dict) else {"raw": body}


def main() -> int:
    failed = 0
    for path in CHECKS:
        try:
            body = fetch(path)
            ok = body.get("ok", True)
            print(f"{'OK' if ok else 'WARN'} {path}")
            if not ok:
                failed += 1
        except Exception as err:  # noqa: BLE001
            print(f"FAIL {path}: {err}")
            failed += 1

    if failed:
        print(f"\n{failed} check(s) failed against {BASE}")
        return 1
    print(f"\nAll checks passed ({BASE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
