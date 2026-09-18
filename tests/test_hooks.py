"""Client hook tests."""

from __future__ import annotations

from unittest.mock import patch

from sentinel_stack.hooks import verify_transaction_intent


def test_hook_blocks_high_gas() -> None:
    out = verify_transaction_intent({"gas_price_gwei": 9999, "signature": "test"})
    assert out["allowed"] is False
    assert out["fail_closed"] is True


def test_hook_allows_when_status_ok() -> None:
    fake_status = {
        "ok": True,
        "blockers": [],
        "networks": {},
    }
    with patch("sentinel_stack.hooks._http_json", return_value=fake_status):
        out = verify_transaction_intent({"gas_price_gwei": 50, "signature": "test"})
    assert out["allowed"] is True
