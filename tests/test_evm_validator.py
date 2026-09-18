"""Universal EVM safety gate tests."""

from __future__ import annotations

from sentinel_stack.evm_validator import safety_commitment, validate_safety_payload


def test_safety_commitment_roundtrip() -> None:
    tx = "0x55a298bfda90213bfe88e9d0231aa3b29c928de431ba28dbd829377c9274291"
    token = safety_commitment(tx, 75_000.0, 0)
    out = validate_safety_payload(
        {
            "tx_hash": tx,
            "public_inputs": {"target_hub_reserve_usd": 75_000.0, "block_height_drift": 0},
            "commitment_token": token,
        }
    )
    assert out["allowed"] is True
    assert out["not_on_chain_zk"] is True


def test_low_reserve_trips_breaker() -> None:
    tx = "0xabc"
    out = validate_safety_payload(
        {
            "tx_hash": tx,
            "public_inputs": {"target_hub_reserve_usd": 1.0, "block_height_drift": 0},
            "commitment_token": safety_commitment(tx, 1.0, 0),
        }
    )
    assert out["allowed"] is False
    assert out["circuit_breaker_tripped"] is True
