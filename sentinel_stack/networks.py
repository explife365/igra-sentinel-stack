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
        "deploy_allowed": True,
        "not_mainnet": True,
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
    }


def wallet_connect_config() -> dict[str, Any]:
    galleon = galleon_profile()
    project_id = (os.environ.get("WALLETCONNECT_PROJECT_ID") or "").strip()
    return {
        "ok": True,
        "not_mainnet": True,
        "network": galleon["wallet_network"],
        "gas_price_wei": GALLEON_MIN_GAS_WEI,
        "gas_price_hex": hex(GALLEON_MIN_GAS_WEI),
        "connectors": {
            "injected": {"enabled": True, "eip6963": True},
            "walletconnect": {
                "enabled": bool(project_id),
                "project_id": project_id or None,
                "hint": (
                    "Set WALLETCONNECT_PROJECT_ID in kaspa.env (https://cloud.reown.com)"
                    if not project_id
                    else None
                ),
            },
        },
        "metadata": {
            "name": "Igra Sentinel Stack",
            "description": "Galleon testnet wallet connect — keys stay local",
            "url": "http://127.0.0.1:8790/ui/dex",
            "icons": [],
        },
        "sign_methods": ["eth_sendTransaction", "personal_sign"],
    }
