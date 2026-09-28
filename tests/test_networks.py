"""WalletConnect public origin tests."""

from __future__ import annotations

from sentinel_stack.networks import (
    foreign_origin_header,
    galleon_profile,
    igra_mainnet_profile,
    public_origin,
    wallet_connect_config,
)


def test_profiles_do_not_advertise_deploy() -> None:
    galleon = galleon_profile()
    mainnet = igra_mainnet_profile()
    assert galleon["chain_id"] == 38836
    assert galleon["deploy_allowed"] is False
    assert mainnet["chain_id"] == 38833
    assert mainnet["deploy_allowed"] is False


def test_default_origin_is_loopback(monkeypatch) -> None:
    monkeypatch.delenv("SENTINEL_PUBLIC_ORIGIN", raising=False)
    assert public_origin() == "http://127.0.0.1:8790"


def test_wallet_connect_uses_public_origin(monkeypatch) -> None:
    monkeypatch.delenv("WALLETCONNECT_PROJECT_ID", raising=False)
    monkeypatch.setenv("SENTINEL_PUBLIC_ORIGIN", "https://sentinel.tuce.app")
    cfg = wallet_connect_config()
    assert cfg["public_origin"] == "https://sentinel.tuce.app"
    assert cfg["metadata"]["url"] == "https://sentinel.tuce.app/ui/dex"
    assert cfg["not_mainnet"] is True
    assert cfg["broadcast_offered"] is False
    assert cfg["sign_methods"] == ["personal_sign"]
    assert cfg["connectors"]["walletconnect"]["enabled"] is False
    assert cfg["connectors"]["walletconnect"]["project_id"] is None


def test_request_host_selects_origin(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_PUBLIC_ORIGIN", "https://sentinel.tuce.app")
    assert public_origin("dex.tuce.app") == "https://dex.tuce.app"
    assert public_origin("cex.tuce.app:443") == "https://cex.tuce.app"
    assert public_origin("sentinel.tuce.app") == "https://sentinel.tuce.app"


def test_foreign_host_is_not_an_origin(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_PUBLIC_ORIGIN", "https://evil.example")
    assert public_origin("evil.example") == "http://127.0.0.1:8790"
    assert public_origin("dex.tuce.app.evil.com") == "http://127.0.0.1:8790"
    assert public_origin("sentinel.tuce.app:8790") == "http://127.0.0.1:8790"
    assert public_origin(None) == "http://127.0.0.1:8790"
    assert public_origin("127.0.0.1:8790", "https://evil.example") == "http://127.0.0.1:8790"


def test_allowlisted_origin_header_on_loopback(monkeypatch) -> None:
    monkeypatch.delenv("SENTINEL_PUBLIC_ORIGIN", raising=False)
    assert public_origin("127.0.0.1:8790", "https://dex.tuce.app") == "https://dex.tuce.app"
    assert foreign_origin_header("https://evil.example") is True
    assert foreign_origin_header("https://dex.tuce.app") is False
    assert foreign_origin_header(None) is False
