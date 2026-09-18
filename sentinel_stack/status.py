"""Sentinel status — dual-network probes + capability registry."""

from __future__ import annotations

from typing import Any

from sentinel_stack.igra_ecosystem import igra_ecosystem_catalog
from sentinel_stack.networks import galleon_profile, igra_mainnet_profile
from sentinel_stack.rpc import probe_chain


def sentinel_status() -> dict[str, Any]:
    galleon = galleon_profile()
    mainnet = igra_mainnet_profile()

    g_probe = probe_chain(galleon["rpc"], galleon["chain_id"])
    m_probe = probe_chain(mainnet["rpc"], mainnet["chain_id"])

    blockers: list[str] = []
    if not g_probe.get("reachable"):
        blockers.append("Galleon testnet RPC unreachable")
    elif not g_probe.get("rpc_writable"):
        blockers.append("Galleon RPC read-only — on-chain deploys blocked")
    if not m_probe.get("reachable"):
        blockers.append("Igra mainnet RPC unreachable")

    eco = igra_ecosystem_catalog()

    return {
        "ok": True,
        "not_mainnet_production": True,
        "not_consensus": True,
        "not_partnership": True,
        "headline": (
            "Igra Sentinel Stack — Galleon testnet rehearsal + Igra mainnet read probes"
        ),
        "active_profile": galleon["id"],
        "networks": {
            "galleon_testnet": {**galleon, "probe": g_probe},
            "igra_mainnet": {**mainnet, "probe": m_probe},
        },
        "implemented": [
            {"id": "evm_safety_gate", "endpoint": "POST /v1/evm/safety-verify"},
            {"id": "katbridge_verify", "endpoint": "POST /v1/funding/bridge-verify"},
            {"id": "igra_ecosystem", "endpoint": "GET /v1/igra/ecosystem"},
            {"id": "network_probes", "endpoint": "GET /v1/networks"},
            {"id": "wallet_connect", "endpoint": "GET /v1/dex/wallet/connect-config", "ui": "/ui/dex"},
            {"id": "client_hooks", "cli": "python -m sentinel_stack.hooks"},
        ],
        "not_shipped": [
            {"id": "on_chain_zk", "note": "SHA-256 commitments only — not SilverScript ZK"},
            {"id": "mainnet_deploy", "note": "No FeePool/hub deploy on chain 38833 in this repo"},
            {"id": "full_dex_router", "note": "Use kaspa-frontier-engine for swap execution"},
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
