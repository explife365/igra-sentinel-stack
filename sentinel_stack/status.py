"""Sentinel status — dual-network probes + capability registry."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sentinel_stack.igra_ecosystem import igra_ecosystem_catalog
from sentinel_stack.networks import galleon_profile, igra_mainnet_profile, public_surfaces
from sentinel_stack.rpc import probe_chain


def _walletconnect_configured() -> bool:
    return bool((os.environ.get("WALLETCONNECT_PROJECT_ID") or "").strip())


def _mark_probe(probe: dict[str, Any]) -> dict[str, Any]:
    """Remote RPC facts stay. This host does not gain a write capability from them."""
    marked = dict(probe)
    marked["host_writes"] = False
    return marked


def sentinel_status() -> dict[str, Any]:
    galleon = galleon_profile()
    mainnet = igra_mainnet_profile()

    with ThreadPoolExecutor(max_workers=2) as pool:
        g_fut = pool.submit(probe_chain, galleon["rpc"], galleon["chain_id"])
        m_fut = pool.submit(probe_chain, mainnet["rpc"], mainnet["chain_id"])
        g_probe = g_fut.result()
        m_probe = m_fut.result()

    blockers: list[str] = []
    if not g_probe.get("reachable"):
        blockers.append("Galleon testnet RPC unreachable")
    elif g_probe.get("rpc_writable") is False:
        blockers.append("Galleon RPC is read-only")
    if not m_probe.get("reachable"):
        blockers.append("Igra mainnet RPC unreachable")
    if galleon.get("deploy_allowed") is not False or mainnet.get("deploy_allowed") is not False:
        blockers.append("A profile advertises deploy_allowed. This host does not deploy.")

    eco = igra_ecosystem_catalog()
    wc_note = (
        "WalletConnect project id is set. Broadcast is not offered."
        if _walletconnect_configured()
        else "WalletConnect is disabled. This host does not invent a project id."
    )

    return {
        "ok": True,
        "not_mainnet_production": True,
        "not_consensus": True,
        "not_partnership": True,
        "headline": (
            "Igra Sentinel Stack — Galleon testnet rehearsal + Igra mainnet read probes"
        ),
        "active_profile": galleon["id"],
        "this_host": {
            "deploy_allowed": False,
            "broadcast_shipped": False,
            "custody_started": False,
            "walletconnect_enabled": _walletconnect_configured(),
            "on_chain_zk": False,
            "hub_seed_balances": False,
        },
        "networks": {
            "galleon_testnet": {**galleon, "probe": _mark_probe(g_probe)},
            "igra_mainnet": {**mainnet, "probe": _mark_probe(m_probe)},
        },
        "implemented": [
            {"id": "evm_safety_gate", "endpoint": "POST /v1/evm/safety-verify"},
            {"id": "katbridge_verify", "endpoint": "POST /v1/funding/bridge-verify"},
            {"id": "igra_ecosystem", "endpoint": "GET /v1/igra/ecosystem"},
            {"id": "network_probes", "endpoint": "GET /v1/networks"},
            {"id": "dex_rehearsal", "endpoint": "GET /v1/dex/wallet/connect-config", "ui": "/ui/dex"},
            {"id": "cex_rehearsal", "endpoint": "GET /v1/cex/status", "ui": "/ui/cex"},
            {"id": "client_hooks", "cli": "python -m sentinel_stack.hooks"},
        ],
        "public_surfaces": public_surfaces(),
        "not_shipped": [
            {"id": "on_chain_zk", "note": "SHA-256 commitments only — not SilverScript ZK"},
            {"id": "host_deploy", "note": "This host does not deploy on chain 38836 or 38833"},
            {"id": "mainnet_deploy", "note": "No FeePool/hub deploy on chain 38833 in this repo"},
            {"id": "full_dex_router", "note": "Swap broadcast is not shipped on this host"},
            {"id": "cex_custody", "note": "Custody is not started. No orders, withdrawals, or broadcast"},
            {"id": "hub_seed_balances", "note": "gTEST-tUSDC seeding state is not reported by this API"},
            {"id": "walletconnect", "note": wc_note},
            {
                "id": "owned_node_synced",
                "note": "Owned-node sync is not claimed here. The CEX gate reads only 127.0.0.1:18210 on this host.",
            },
        ],
        "blockers": blockers,
        "ecosystem": {
            "profiles": [p["id"] for p in eco.get("compatibility_profiles", [])],
        },
        "upstream": {
            "full_integrator": "https://github.com/explife365/kaspa-frontier-engine",
            "dex_terminal": "kaspa-frontier-engine/projects/kaspa-dex-terminal",
        },
    }
