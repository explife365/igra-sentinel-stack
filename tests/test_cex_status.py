"""Fail-closed CEX status and loopback probe shaping."""

from __future__ import annotations

import os

from sentinel_stack.cex_status import cex_rehearsal_status, owned_node_gate
from sentinel_stack.tn10_probe import probe_tn10_loopback, summarize_wrpc


def test_summarize_drops_unlisted_fields() -> None:
    body = summarize_wrpc(
        {"params": {"isSynced": False, "networkId": "testnet-10", "peers": ["1.2.3.4"]}},
        {"params": {"headerCount": 500, "blockCount": 20, "peerInfo": [{"ip": "9.9.9.9"}]}},
    )
    assert body["network_id"] == "testnet-10"
    assert body["is_synced"] is False
    assert body["header_count"] == 500
    assert body["block_count"] == 20
    assert body["sync_note"] == "header count is ahead of block count"
    assert "peers" not in body
    assert "peerInfo" not in body


def test_probe_refused(monkeypatch) -> None:
    def refuse(*_args, **_kwargs):
        raise ConnectionRefusedError

    monkeypatch.setattr("sentinel_stack.tn10_probe.socket.create_connection", refuse)
    body = probe_tn10_loopback()
    assert body["listening"] is False
    assert body["exposed_publicly"] is False
    assert body["proxied"] is False
    assert body["error"] == "not_listening"
    assert body["target"] == "127.0.0.1:18210"


def test_cex_status_fail_closed(monkeypatch) -> None:
    for key in list(os.environ):
        if "PRIVATE_KEY" in key:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "sentinel_stack.cex_status.probe_tn10_loopback",
        lambda: {"listening": False, "answered": False, "exposed_publicly": False, "proxied": False},
    )
    monkeypatch.setattr("sentinel_stack.cex_status.custody_port_open", lambda: False)
    body = cex_rehearsal_status()
    assert body["custody_started"] is False
    assert body["actions_enabled"] is False
    assert body["orders"] == "not_shipped"
    assert body["withdrawals"] == "not_shipped"
    assert body["broadcast"] == "not_shipped"
    assert body["owned_node_gate"]["status"] == "red"
    assert body["owned_node_gate"]["local_synced"] is False
    assert body["private_key_in_process_env"] is False
    assert body["custody_listener"]["open"] is False
    assert body["not_partnership"] is True
    assert body["not_consensus"] is True
    assert body["not_mainnet_production"] is True
    assert "evil.example" not in body["public_origin"]


def test_cex_status_ignores_foreign_origin_header(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel_stack.cex_status.probe_tn10_loopback",
        lambda: {"listening": False, "answered": False, "exposed_publicly": False, "proxied": False},
    )
    monkeypatch.setattr("sentinel_stack.cex_status.custody_port_open", lambda: False)
    body = cex_rehearsal_status("127.0.0.1:8790", "https://evil.example")
    assert body["public_origin"] == "http://127.0.0.1:8790"


def test_synced_loopback_does_not_open_custody() -> None:
    gate = owned_node_gate(
        {
            "listening": True,
            "answered": True,
            "is_synced": True,
            "exposed_publicly": False,
            "proxied": False,
        }
    )
    assert gate["local_synced"] is True
    assert gate["status"] == "red"


def test_other_host_sync_does_not_open_the_gate() -> None:
    gate = owned_node_gate(
        {
            "listening": True,
            "answered": True,
            "is_synced": False,
            "exposed_publicly": False,
            "proxied": False,
        }
    )
    assert gate["local_synced"] is False
    assert gate["status"] == "red"


def test_probe_returns_when_peer_stalls() -> None:
    import socket
    import threading
    import time

    from sentinel_stack import tn10_probe

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    held: list[socket.socket] = []

    def accept_and_stall() -> None:
        conn, _addr = server.accept()
        held.append(conn)
        time.sleep(2.5)
        conn.close()

    thread = threading.Thread(target=accept_and_stall, daemon=True)
    thread.start()
    original = tn10_probe.TARGET_PORT
    tn10_probe.TARGET_PORT = port
    started = time.monotonic()
    try:
        body = tn10_probe.probe_tn10_loopback(timeout_s=0.4)
    finally:
        tn10_probe.TARGET_PORT = original
        server.close()
        for conn in held:
            try:
                conn.close()
            except OSError:
                pass
    elapsed = time.monotonic() - started
    assert elapsed < 1.5
    assert body["answered"] is False
    assert body["proxied"] is False
    assert body["exposed_publicly"] is False
    assert body["target"].startswith("127.0.0.1:")


def test_integrator_sync_field(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel_stack.cex_status.probe_tn10_loopback",
        lambda: {"listening": False, "answered": False, "exposed_publicly": False, "proxied": False},
    )
    monkeypatch.setattr("sentinel_stack.cex_status.custody_port_open", lambda: False)
    body = cex_rehearsal_status()
    sync = body.get("integrator_sync") or {}
    assert sync.get("public_exposure") is False
    assert sync.get("custody_on_this_host") is False
    assert "host03" in (sync.get("summary") or "")
