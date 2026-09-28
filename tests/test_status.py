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


def test_sentinel_status_shape(monkeypatch) -> None:
    monkeypatch.delenv("WALLETCONNECT_PROJECT_ID", raising=False)
    with patch("sentinel_stack.status.probe_chain", side_effect=_fake_probe_ok):
        body = sentinel_status()
    assert body["ok"] is True
    assert body["not_partnership"] is True
    assert len(body["implemented"]) >= 5
    assert "galleon_testnet" in body["networks"]
    galleon = body["networks"]["galleon_testnet"]
    mainnet = body["networks"]["igra_mainnet"]
    assert galleon["deploy_allowed"] is False
    assert galleon["chain_id"] == 38836
    assert mainnet["deploy_allowed"] is False
    assert mainnet["chain_id"] == 38833
    assert galleon["probe"]["host_writes"] is False
    assert mainnet["probe"]["host_writes"] is False
    assert galleon["probe"]["rpc_writable"] is True
    implemented = [item["id"] for item in body["implemented"]]
    assert "wallet_connect" not in implemented
    assert "walletconnect" not in implemented
    missing = {item["id"] for item in body["not_shipped"]}
    assert {"walletconnect", "on_chain_zk", "cex_custody", "hub_seed_balances", "host_deploy"} <= missing
    host = body["this_host"]
    assert host["deploy_allowed"] is False
    assert host["broadcast_shipped"] is False
    assert host["custody_started"] is False
    assert host["walletconnect_enabled"] is False
    assert host["on_chain_zk"] is False
    assert host["hub_seed_balances"] is False


def test_igra_ecosystem_refusal() -> None:
    body = igra_ecosystem_catalog()
    joined = " ".join(body["refusal"]).lower()
    assert "partner" in joined
