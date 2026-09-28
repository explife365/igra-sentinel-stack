"""Client-side Sentinel gate — query local API before broadcast (fail-closed)."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE = os.environ.get("SENTINEL_API_BASE", "http://127.0.0.1:8790").rstrip("/")
MAX_GAS_GWEI = float(os.environ.get("SENTINEL_MAX_GAS_GWEI", "250"))


def _http_json(
    url: str,
    timeout: float = 8.0,
    method: str = "GET",
    body: dict | None = None,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json", "User-Agent": "igra-sentinel-stack/hook"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            parsed = json.loads(resp.read(256_000).decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"error": raw[:300]}
        if isinstance(parsed, dict):
            parsed.setdefault("ok", False)
            parsed["http_status"] = err.code
            return parsed
        return {"ok": False, "http_status": err.code, "error": raw[:300]}
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "error": str(err), "fail_closed": True}


def verify_transaction_intent(
    tx_payload: dict[str, Any],
    *,
    sentinel_base: str = DEFAULT_BASE,
) -> dict[str, Any]:
    gas = float(tx_payload.get("gas_price_gwei") or tx_payload.get("gas_gwei") or 0)
    sig = str(tx_payload.get("signature") or tx_payload.get("tx_id") or "unknown")
    reasons: list[str] = []

    if gas > MAX_GAS_GWEI:
        reasons.append(f"gas {gas} gwei exceeds cap {MAX_GAS_GWEI}")

    status = _http_json(f"{sentinel_base}/v1/sentinel/status", timeout=8.0)
    if not status.get("ok"):
        return {
            "ok": False,
            "allowed": False,
            "fail_closed": True,
            "reasons": ["sentinel status unreachable"],
            "signature": sig,
            "status": status,
        }

    blockers = status.get("blockers") or []
    if blockers:
        reasons.extend([f"blocker:{b}" for b in blockers])

    networks = status.get("networks")
    deploy_ok = False
    if isinstance(networks, dict):
        for net in networks.values():
            if isinstance(net, dict) and net.get("deploy_allowed") is True:
                deploy_ok = True
                break
    if not deploy_ok:
        reasons.append("deploy_not_allowed_on_this_host")

    host = status.get("this_host")
    if not (isinstance(host, dict) and host.get("broadcast_shipped") is True):
        reasons.append("broadcast_not_shipped")

    allowed = len(reasons) == 0
    return {
        "ok": True,
        "allowed": allowed,
        "fail_closed": not allowed,
        "reasons": reasons,
        "signature": sig,
        "sentinel_base": sentinel_base,
        "networks": status.get("networks"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Igra Sentinel client hook")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--verify-tx", action="store_true")
    parser.add_argument("--gas-gwei", type=float, default=0)
    args = parser.parse_args()

    if args.verify_tx:
        body = verify_transaction_intent(
            {"gas_price_gwei": args.gas_gwei, "signature": "cli"},
            sentinel_base=args.base,
        )
        print(json.dumps(body, indent=2))
        return 0 if body.get("allowed") else 1

    print(json.dumps(_http_json(f"{args.base}/v1/sentinel/status"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
