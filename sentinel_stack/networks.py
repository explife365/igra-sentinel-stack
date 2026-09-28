"""Igra EVM network profiles — Galleon testnet + mainnet metadata."""

from __future__ import annotations

import os
from typing import Any

GALLEON_CHAIN_ID = 38836
GALLEON_RPC = "https://galleon-testnet.igralabs.com:8545"
GALLEON_EXPLORER = "https://explorer.galleon-testnet.igralabs.com"
IGRA_FAUCET = "https://faucet.igralabs.com"

IGRA_MAINNET_CHAIN_ID = 38833
IGRA_MAINNET_RPC = "https://rpc.igralabs.com:8545"
IGRA_MAINNET_EXPLORER = "https://explorer.igralabs.com"
IGRA_MAINNET_HYPERLANE_USDC = "0xA5b8BF902b2844dA17d4506cc827F7F1681735E7"

# Exact request Host values accepted for public origin and metadata.
PUBLIC_HOSTS = frozenset({"sentinel.tuce.app", "dex.tuce.app", "cex.tuce.app"})
CANONICAL_PUBLIC_HOST = "sentinel.tuce.app"
_ORIGIN_PORTS = frozenset({"80", "443"})

GALLEON_ENTRY_ADDRESS = (
    "kaspatest:qqmstl2znv9tsfgcmj9shme82my867tapz7pdu4ztwdn6sm9452jj5mm0sxzw"
)
GALLEON_TXID_PREFIX = "97b4"
GALLEON_MIN_GAS_WEI = 2_000_000_000_000  # 2000 gwei floor


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    return int(raw) if raw else default


def _str_env(name: str, default: str) -> str:
    return (os.environ.get(name) or default).strip()


def galleon_profile() -> dict[str, Any]:
    chain_id = _int_env("GALLEON_CHAIN_ID", GALLEON_CHAIN_ID)
    rpc = _str_env("GALLEON_RPC", GALLEON_RPC)
    return {
        "id": "galleon-testnet",
        "name": "Igra Galleon Testnet",
        "layer": "L2-EVM",
        "chain_id": chain_id,
        "chain_id_hex": f"0x{chain_id:x}",
        "rpc": rpc,
        "explorer": GALLEON_EXPLORER,
        "faucet": IGRA_FAUCET,
        "native_symbol": "iKAS",
        "rehearsal_target": True,
        "deploy_allowed": False,
        "not_mainnet": True,
        "note": "This host does not deploy. Chain 38836 may stay reachable.",
        "wallet_network": {
            "chainId": f"0x{chain_id:x}",
            "chainIdDecimal": chain_id,
            "chainName": "Igra Galleon Testnet",
            "nativeCurrency": {"name": "iKAS", "symbol": "iKAS", "decimals": 18},
            "rpcUrls": [rpc],
            "blockExplorerUrls": [GALLEON_EXPLORER],
        },
    }


def igra_mainnet_profile() -> dict[str, Any]:
    chain_id = _int_env("IGRA_MAINNET_CHAIN_ID", IGRA_MAINNET_CHAIN_ID)
    rpc = _str_env("IGRA_MAINNET_RPC", IGRA_MAINNET_RPC)
    return {
        "id": "igra-mainnet",
        "name": "Igra Mainnet EVM",
        "layer": "L2-EVM",
        "chain_id": chain_id,
        "chain_id_hex": f"0x{chain_id:x}",
        "rpc": rpc,
        "explorer": IGRA_MAINNET_EXPLORER,
        "native_symbol": "iKAS",
        "rehearsal_target": False,
        "deploy_allowed": False,
        "not_mainnet": False,
        "hyperlane_usdc": IGRA_MAINNET_HYPERLANE_USDC,
        "circle_usdc_listed": False,
        "note": "read-only probes in this stack — no production deploy",
    }


def networks_catalog() -> dict[str, Any]:
    profile = (os.environ.get("SENTINEL_NETWORK_PROFILE") or "galleon-testnet").strip()
    return {
        "ok": True,
        "active_profile": profile,
        "not_partnership": True,
        "not_endorsement": True,
        "networks": [galleon_profile(), igra_mainnet_profile()],
        "kip21_entry": {
            "address": GALLEON_ENTRY_ADDRESS,
            "txid_prefix": GALLEON_TXID_PREFIX,
            "ui": "https://ikas.katbridge.com/",
        },
        "canonical_public_origin": f"https://{CANONICAL_PUBLIC_HOST}",
        "public_surfaces": public_surfaces(),
    }


def public_surfaces() -> list[dict[str, str]]:
    return [
        {
            "id": "sentinel",
            "host": "sentinel.tuce.app",
            "origin": "https://sentinel.tuce.app",
            "role": "primary status",
        },
        {
            "id": "dex",
            "host": "dex.tuce.app",
            "origin": "https://dex.tuce.app",
            "role": "galleon testnet rehearsal",
        },
        {
            "id": "cex",
            "host": "cex.tuce.app",
            "origin": "https://cex.tuce.app",
            "role": "fail-closed custody rehearsal",
        },
    ]


def allowed_host(host_header: str | None) -> str | None:
    """Return the hostname only when it is exactly one of the public names."""
    if not host_header:
        return None
    raw = host_header.split(",")[0].strip().lower()
    if not raw or any(ch in raw for ch in " @\\/?#"):
        return None
    if raw.startswith("["):
        return None
    host, sep, port = raw.partition(":")
    if sep and port not in _ORIGIN_PORTS:
        return None
    if host in PUBLIC_HOSTS:
        return host
    return None


def surface_for_host(host_header: str | None) -> str:
    host = allowed_host(host_header)
    if host == "dex.tuce.app":
        return "dex"
    if host == "cex.tuce.app":
        return "cex"
    if host == "sentinel.tuce.app":
        return "sentinel"
    return "operator"


def foreign_origin_header(origin_header: str | None) -> bool:
    """True when a non-empty Origin header is not an allowlisted https public surface."""
    raw = (origin_header or "").strip()
    if not raw or raw.lower() == "null":
        return False
    return _https_allowlisted_host(raw) is None


def _https_allowlisted_host(origin: str) -> str | None:
    from urllib.parse import urlparse

    raw = (origin or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    if parsed.port not in (None, 443):
        return None
    name = (parsed.hostname or "").lower()
    if name in PUBLIC_HOSTS:
        return name
    return None


def public_origin(
    host_header: str | None = None,
    origin_header: str | None = None,
) -> str:
    """Origin for metadata. Request Host wins when it is an allowlisted name.

    A allowlisted ``Origin`` header may apply when ``Host`` is loopback or unknown.
    Foreign ``Origin`` values are never adopted — callers should reject them before
    calling this helper when enforcing fail-closed HTTP behavior.

    ``SENTINEL_PUBLIC_ORIGIN`` is used only when its host is also allowlisted.
    """
    host = allowed_host(host_header)
    if host:
        return f"https://{host}"
    from_origin = _https_allowlisted_host((origin_header or "").strip())
    if from_origin:
        return f"https://{from_origin}"
    fallback = _https_allowlisted_host(_str_env("SENTINEL_PUBLIC_ORIGIN", ""))
    if fallback:
        return f"https://{fallback}"
    return "http://127.0.0.1:8790"


def wallet_connect_config(
    host_header: str | None = None,
    origin_header: str | None = None,
) -> dict[str, Any]:
    galleon = galleon_profile()
    project_id = (os.environ.get("WALLETCONNECT_PROJECT_ID") or "").strip()
    origin = public_origin(host_header, origin_header)
    enabled = bool(project_id)
    return {
        "ok": True,
        "not_mainnet": True,
        "broadcast_offered": False,
        "public_origin": origin,
        "network": galleon["wallet_network"],
        "gas_price_wei": GALLEON_MIN_GAS_WEI,
        "gas_price_hex": hex(GALLEON_MIN_GAS_WEI),
        "connectors": {
            "injected": {"enabled": True, "eip6963": True},
            "walletconnect": {
                "enabled": enabled,
                "project_id": project_id or None,
                "hint": (
                    "WalletConnect is disabled until WALLETCONNECT_PROJECT_ID is set. "
                    "This host will not invent a project id."
                    if not enabled
                    else None
                ),
            },
        },
        "metadata": {
            "name": "Igra Sentinel",
            "description": "Galleon testnet rehearsal — keys stay in the wallet",
            "url": f"{origin}/ui/dex",
            "icons": [],
        },
        "sign_methods": ["personal_sign"],
    }
