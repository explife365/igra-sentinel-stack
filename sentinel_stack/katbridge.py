"""KatBridge KIP-21 Entry structural validation."""

from __future__ import annotations

import re
from typing import Any

from sentinel_stack.networks import (
    GALLEON_CHAIN_ID,
    GALLEON_ENTRY_ADDRESS,
    GALLEON_TXID_PREFIX,
)

TN10_CHAIN_ID = 10
MAINNET_MARKERS = re.compile(r"\b(mainnet|kaspa:qq[^t]|ethereum\s*mainnet)\b", re.I)


def txid_has_galleon_prefix(txid: str) -> bool:
    return (txid or "").strip().lower().startswith(GALLEON_TXID_PREFIX.lower())


def validate_bridge_intent(
    *,
    tx_id: str,
    source_chain_id: int,
    target_chain_id: int,
    amount_sompi: int = 0,
    proof_note: str = "",
    l2_recipient: str | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    tx = (tx_id or "").strip()

    if source_chain_id == target_chain_id:
        reasons.append("source_chain_id equals target_chain_id (replay risk)")

    if target_chain_id == GALLEON_CHAIN_ID and tx and not txid_has_galleon_prefix(tx):
        reasons.append(f"Galleon Entry requires txid prefix {GALLEON_TXID_PREFIX}")

    if amount_sompi <= 0:
        reasons.append("amount must be positive")

    blob = f"{proof_note} {l2_recipient or ''}".strip()
    if target_chain_id == GALLEON_CHAIN_ID and blob and MAINNET_MARKERS.search(blob):
        reasons.append("mainnet marker in test rehearsal payload")

    if target_chain_id == GALLEON_CHAIN_ID and l2_recipient and not l2_recipient.startswith("0x"):
        reasons.append("Galleon recipient must be 0x EVM address")

    return {
        "ok": True,
        "not_mainnet": True,
        "allowed": len(reasons) == 0,
        "reasons": reasons,
        "entry_address": GALLEON_ENTRY_ADDRESS,
        "txid_prefix_required": GALLEON_TXID_PREFIX,
        "transaction_intent_id": tx or None,
        "source_chain_id": source_chain_id,
        "target_chain_id": target_chain_id,
    }


def validate_bridge_payload(body: dict[str, Any]) -> dict[str, Any]:
    return validate_bridge_intent(
        tx_id=str(body.get("transaction_intent_id") or body.get("tx_id") or ""),
        source_chain_id=int(body.get("source_chain_id") or TN10_CHAIN_ID),
        target_chain_id=int(body.get("target_chain_id") or GALLEON_CHAIN_ID),
        amount_sompi=int(body.get("token_amount_tkas") or body.get("amount_sompi") or 0),
        proof_note=str(body.get("covenant_proof_bytes") or body.get("proof_note") or ""),
        l2_recipient=str(body.get("l2_recipient") or body.get("recipient") or "") or None,
    )
