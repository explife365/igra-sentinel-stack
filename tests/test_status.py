"""Sentinel status and ecosystem shape tests."""

from __future__ import annotations

from unittest.mock import patch

from sentinel_stack.igra_ecosystem import igra_ecosystem_catalog
from sentinel_stack.status import sentinel_status


def _fake_probe_ok(*_args, **_kwargs):
    return {
        "ok": True,
        "reachable": True,
        "chain_id_matches": True,
        "latest_block": 1,
        "rpc_writable": True,
    }


def test_sentinel_status_shape() -> None:
    with patch("sentinel_stack.status.probe_chain", side_effect=_fake_probe_ok):
        body = sentinel_status()
    assert body["ok"] is True
    assert body["not_partnership"] is True
    assert len(body["implemented"]) >= 5
    assert "galleon_testnet" in body["networks"]


def test_igra_ecosystem_refusal() -> None:
    body = igra_ecosystem_catalog()
    joined = " ".join(body["refusal"]).lower()
    assert "partner" in joined
