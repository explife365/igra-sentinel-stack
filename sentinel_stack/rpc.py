"""Minimal JSON-RPC for EVM chain probes."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    req = urllib.request.Request(
        rpc_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body:
        raise RuntimeError(str(body["error"]))
    return body["result"]


def probe_chain(rpc_url: str, expected_chain_id: int) -> dict[str, Any]:
    try:
        chain_hex = rpc_call(rpc_url, "eth_chainId", [])
        block_hex = rpc_call(rpc_url, "eth_blockNumber", [])
        chain_id = int(chain_hex, 16)
        block = int(block_hex, 16)
        writable = True
        try:
            rpc_call(rpc_url, "eth_gasPrice", [])
        except RuntimeError as err:
            if "read-only" in str(err).lower():
                writable = False
        return {
            "ok": True,
            "reachable": True,
            "chain_id": chain_id,
            "chain_id_matches": chain_id == expected_chain_id,
            "latest_block": block,
            "rpc_writable": writable,
            "rpc": rpc_url,
        }
    except Exception as err:  # noqa: BLE001
        return {
            "ok": False,
            "reachable": False,
            "error": str(err),
            "rpc": rpc_url,
            "chain_id_matches": False,
        }
