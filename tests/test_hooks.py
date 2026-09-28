"""Client hook tests."""

from __future__ import annotations

from unittest.mock import patch

from sentinel_stack.hooks import verify_transaction_intent


def test_hook_blocks_high_gas() -> None:
    out = verify_transaction_intent({"gas_price_gwei": 9999, "signature": "test"})
    assert out["allowed"] is False
    assert out["fail_closed"] is True


def test_hook_refuses_when_this_host_cannot_deploy() -> None:
    fake_status = {
        "ok": True,
        "blockers": [],
        "this_host": {"broadcast_shipped": False, "deploy_allowed": False},
        "networks": {
            "galleon_testnet": {"deploy_allowed": False, "chain_id": 38836},
            "igra_mainnet": {"deploy_allowed": False, "chain_id": 38833},
        },
    }
    with patch("sentinel_stack.hooks._http_json", return_value=fake_status):
        out = verify_transaction_intent({"gas_price_gwei": 50, "signature": "test"})
    assert out["allowed"] is False
    assert out["fail_closed"] is True
    assert "deploy_not_allowed_on_this_host" in out["reasons"]
    assert "broadcast_not_shipped" in out["reasons"]


def test_hook_refuses_when_status_omits_capabilities() -> None:
    """A status with ok=true and no explicit ship flags must not open broadcast."""
    fake_status = {
        "ok": True,
        "blockers": [],
        "networks": {},
    }
    with patch("sentinel_stack.hooks._http_json", return_value=fake_status):
        out = verify_transaction_intent({"gas_price_gwei": 50, "signature": "test"})
    assert out["allowed"] is False
    assert out["fail_closed"] is True
    assert "deploy_not_allowed_on_this_host" in out["reasons"]
    assert "broadcast_not_shipped" in out["reasons"]


def test_hook_refuses_when_broadcast_flag_is_absent() -> None:
    fake_status = {
        "ok": True,
        "blockers": [],
        "this_host": {"deploy_allowed": False},
        "networks": {
            "galleon_testnet": {"deploy_allowed": False, "chain_id": 38836},
        },
    }
    with patch("sentinel_stack.hooks._http_json", return_value=fake_status):
        out = verify_transaction_intent({"gas_price_gwei": 50, "signature": "test"})
    assert out["allowed"] is False
    assert "broadcast_not_shipped" in out["reasons"]
    assert "deploy_not_allowed_on_this_host" in out["reasons"]
