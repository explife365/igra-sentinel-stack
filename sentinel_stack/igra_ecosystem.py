"""Igra ecosystem context — independent market validation (no partnership claims)."""

from __future__ import annotations

from typing import Any

from sentinel_stack.networks import GALLEON_CHAIN_ID, IGRA_MAINNET_CHAIN_ID

IGRA_PUBLIC_FACTS = {
    "layer_type": "decentralized EVM-compatible rollup on Kaspa PoW",
    "claimed_tps": "3000+ (marketing; not verified by this repo)",
    "governance": "Swiss association + community DAO (public statements)",
    "galleon_testnet_chain_id": GALLEON_CHAIN_ID,
    "igra_mainnet_chain_id": IGRA_MAINNET_CHAIN_ID,
}

COMPATIBILITY_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "igra_labs",
        "name": "Igra Labs",
        "relationship": "unaffiliated_compatibility_target",
        "technical_profile": "EVM rollup on Kaspa; Galleon testnet + mainnet EVM",
        "integrator_fit": [
            "Dual-network sentinel probes (38836 rehearsal, 38833 read-only)",
            "Universal EVM safety commitment gate",
            "KatBridge KIP-21 structural bridge verify",
        ],
        "not_claimed": "partnership, grant award, or production deployment",
    },
    {
        "id": "kaspagent",
        "name": "Kaspagent",
        "relationship": "unaffiliated_compatibility_target",
        "technical_profile": "AI agent marketplace on Kaspa ecosystem",
        "integrator_fit": ["Client-side sentinel hooks before agent-signed txs"],
        "not_claimed": "integration contract or marketplace listing",
    },
    {
        "id": "rkstratum",
        "name": "RKStratum",
        "relationship": "unaffiliated_compatibility_target",
        "technical_profile": "Community mining / node infrastructure",
        "integrator_fit": ["Block-height drift checks in universal EVM validator"],
        "not_claimed": "node telemetry feed or validator partnership",
    },
)

OPEN_CORE_TIERS: tuple[dict[str, Any], ...] = (
    {
        "capability": "structural_safety_gates",
        "open_source": "KatBridge + universal EVM commitment checks",
        "enterprise": "Live ruleset feed + SLA-backed response",
    },
    {
        "capability": "network_probes",
        "open_source": "Galleon + Igra mainnet RPC health",
        "enterprise": "Multi-region quorum dashboards",
    },
    {
        "capability": "legal_warranties_sla",
        "open_source": "As-is rehearsal stack",
        "enterprise": "Commercial license / BSL gate (external)",
    },
)


def igra_ecosystem_catalog() -> dict[str, Any]:
    return {
        "ok": True,
        "not_partnership": True,
        "not_grant_recipient": True,
        "not_endorsement": True,
        "galleon_chain_id": GALLEON_CHAIN_ID,
        "igra_mainnet_chain_id": IGRA_MAINNET_CHAIN_ID,
        "igra_public_facts": IGRA_PUBLIC_FACTS,
        "compatibility_profiles": list(COMPATIBILITY_PROFILES),
        "open_core_tiers": list(OPEN_CORE_TIERS),
        "endpoints": {
            "ecosystem": "GET /v1/igra/ecosystem",
            "evm_safety": "POST /v1/evm/safety-verify",
            "bridge": "POST /v1/funding/bridge-verify",
            "sentinel": "GET /v1/sentinel/status",
            "networks": "GET /v1/networks",
        },
        "refusal": [
            "Do not present Igra/Kaspagent/RKStratum as launch partners",
            "Do not claim grant funding or Swiss DAO approval",
            "Do not label SHA-256 commitments as on-chain ZK proofs",
        ],
    }
