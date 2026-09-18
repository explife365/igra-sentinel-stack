"""KatBridge structural validation tests."""

from __future__ import annotations

from sentinel_stack.katbridge import validate_bridge_intent, validate_bridge_payload


def test_bridge_replay_blocked() -> None:
    out = validate_bridge_intent(
        tx_id="abc",
        source_chain_id=38836,
        target_chain_id=38836,
        amount_sompi=100_000_000,
    )
    assert out["allowed"] is False


def test_bridge_clean_tn10_to_galleon() -> None:
    out = validate_bridge_payload(
        {
            "transaction_intent_id": "97b4deadbeef",
            "source_chain_id": 10,
            "target_chain_id": 38836,
            "token_amount_tkas": 100_000_000,
            "covenant_proof_bytes": "kaspatest:proof",
            "l2_recipient": "0xb39f360Afc72908b89AA3413cF0e2Eb6D20B4B23",
        }
    )
    assert out["allowed"] is True
