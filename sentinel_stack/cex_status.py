"""Fail-closed CEX rehearsal status.

Read-only and fast. No orders, withdrawals, broadcasts, or custody startup.
The owned-node gate stays red on this public host.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any

from sentinel_stack.networks import public_origin
from sentinel_stack.tn10_probe import probe_tn10_loopback

CUSTODY_PORT = 8787
_INTEGRATOR_HINT = (
    "TN10 owned-gate sync and CEX readiness run on the host03 integrator at "
    "127.0.0.1:8788 (not exposed on the public internet). Public CEX custody is "
    "not started on cex.tuce.app; this gate stays red by design."
)


def custody_port_open(timeout_s: float = 0.25) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", CUSTODY_PORT), timeout=timeout_s):
            return True
    except OSError:
        return False


def integrator_rehearsal_sync(timeout_s: float = 1.0) -> dict[str, Any]:
    """Honest multi-host status. Optional internal probe via INTEGRATOR_REACH_URL."""
    body: dict[str, Any] = {
        "host": "host03",
        "integrator_service": "kaspa-integrator-api",
        "loopback": "127.0.0.1:8788",
        "public_exposure": False,
        "custody_on_this_host": False,
        "summary": _INTEGRATOR_HINT,
    }
    url = (os.environ.get("INTEGRATOR_REACH_URL") or "").strip()
    if not url:
        body["probe"] = "not_configured"
        return body
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read(8192).decode("utf-8"))
        gate = payload.get("owned_gate") if isinstance(payload, dict) else {}
        if not isinstance(gate, dict):
            gate = {}
        body["probe"] = "ok"
        body["reachable"] = True
        body["owned_gate_green"] = gate.get("green")
        body["public_rest_ok"] = (payload.get("public_rest") or {}).get("ok") if isinstance(payload, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as err:
        body["probe"] = "unreachable"
        body["reachable"] = False
        body["error"] = str(err)[:180]
    return body


def owned_node_gate(tn10: dict[str, Any]) -> dict[str, Any]:
    """Public gate stays red. local_synced is this host's loopback reading only.

    Another machine does not count. A synced loopback socket does not start custody.
    """
    local_synced = (
        tn10.get("listening") is True
        and tn10.get("answered") is True
        and tn10.get("is_synced") is True
        and tn10.get("exposed_publicly") is not True
        and tn10.get("proxied") is not True
    )
    if local_synced:
        return {
            "status": "red",
            "local_synced": True,
            "reason": (
                "Loopback wRPC on this host reports synced. "
                "Custody is not started, so this public gate stays red. "
                + _INTEGRATOR_HINT
            ),
        }
    return {
        "status": "red",
        "local_synced": False,
        "reason": (
            "Red. 127.0.0.1:18210 on this host is not synced. "
            "A synced node on another machine does not count. Custody is not started. "
            + _INTEGRATOR_HINT
        ),
    }


def cex_rehearsal_status(
    host_header: str | None = None,
    origin_header: str | None = None,
) -> dict[str, Any]:
    key_present = any("PRIVATE_KEY" in name for name in os.environ)
    tn10 = probe_tn10_loopback()
    return {
        "ok": True,
        "surface": "cex",
        "public_origin": public_origin(host_header, origin_header),
        "fail_closed": True,
        "not_partnership": True,
        "not_consensus": True,
        "not_mainnet_production": True,
        "not_cex_custody": True,
        "custody_started": False,
        "orders": "not_shipped",
        "withdrawals": "not_shipped",
        "broadcast": "not_shipped",
        "actions_enabled": False,
        "private_key_in_process_env": key_present,
        "owned_node_gate": owned_node_gate(tn10),
        "integrator_sync": integrator_rehearsal_sync(),
        "custody_listener": {
            "port": CUSTODY_PORT,
            "open": custody_port_open(),
            "started_by_sentinel": False,
        },
        "tn10": tn10,
    }
