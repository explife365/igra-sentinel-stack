"""Galleon trading console rehearsal (sentinel mirror). Chain 38836 only."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from sentinel_stack.rpc import rpc_call

GALLEON_CHAIN_ID = 38836
GALLEON_RPC_DEFAULT = "https://galleon-testnet.igralabs.com:8545"

ROOT_DISCLAIMER = (
    "Galleon testnet rehearsal only (chain 38836). Not mainnet production. "
    "Not consensus. Not an Igra partnership. No live trading until operator ships contracts. "
    "No MEV or front-running. Wallet automation is client-side with user-approved WalletConnect only."
)

SETTLEMENT_INTERVAL_SECS = 8 * 3600
STACK_ROOT = Path(__file__).resolve().parents[1]

_VOLUME_BANDS: tuple[tuple[float, float, int, int], ...] = (
    (0.0, 10_000.0, 30, 0),
    (10_000.0, 100_000.0, 25, 5),
    (100_000.0, 1_000_000.0, 20, 10),
    (1_000_000.0, math.inf, 15, 15),
)

_REHEARSAL_LEADERBOARD: tuple[dict[str, Any], ...] = (
    {"wallet": "0xa1111111111111111111111111111111111111111", "volume_30d_gtest": 2_450_000.0, "trades": 1842},
    {"wallet": "0xb2222222222222222222222222222222222222222", "volume_30d_gtest": 1_120_000.0, "trades": 903},
    {"wallet": "0xc3333333333333333333333333333333333333333", "volume_30d_gtest": 640_000.0, "trades": 512},
)


def _rehearsal_flags() -> dict[str, Any]:
    return {
        "ok": True,
        "chain_id": GALLEON_CHAIN_ID,
        "not_mainnet": True,
        "not_consensus": True,
        "not_partnership": True,
        "not_shipped": True,
        "deploy_allowed": False,
        "live_trading": False,
        "disclaimer": ROOT_DISCLAIMER,
    }


def _leaderboard_path() -> Path:
    raw = (os.environ.get("GALLEON_LEADERBOARD_PATH") or "").strip()
    if raw:
        return Path(raw)
    return STACK_ROOT / ".local" / "galleon_leaderboard.json"


def _mock_volume_30d(wallet: str | None) -> float:
    if wallet:
        per_wallet = (os.environ.get(f"TRADING_VOLUME_30D_{wallet.lower()}") or "").strip()
        if per_wallet:
            try:
                return max(0.0, float(per_wallet))
            except ValueError:
                pass
    env_vol = (os.environ.get("TRADING_REHEARSAL_VOLUME_30D") or "").strip()
    if env_vol:
        try:
            return max(0.0, float(env_vol))
        except ValueError:
            pass
    if wallet:
        digest = hashlib.sha256(wallet.lower().encode()).hexdigest()
        return float(int(digest[:8], 16) % 500_000) + 1_000.0
    return 12_500.0


def volume_tiers(wallet: str | None = None) -> dict[str, Any]:
    vol = _mock_volume_30d(wallet)
    tier_id = "starter"
    maker_fee_bps = 30
    rebate_bps = 0
    for idx, (lo, hi, fee, rebate) in enumerate(_VOLUME_BANDS):
        if lo <= vol < hi:
            tier_id = ("starter", "silver", "gold", "platinum")[idx]
            maker_fee_bps = fee
            rebate_bps = rebate
            break
    bands = [
        {
            "tier_id": ("starter", "silver", "gold", "platinum")[i],
            "min_30d_volume_gtest": lo,
            "max_30d_volume_gtest": None if hi == math.inf else hi,
            "maker_fee_bps": fee,
            "volume_rebate_bps": rebate,
        }
        for i, (lo, hi, fee, rebate) in enumerate(_VOLUME_BANDS)
    ]
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_trading_volume_rewards",
            "window_days": 30,
            "volume_source": "rehearsal_mock",
            "wallet": wallet,
            "volume_30d_gtest_equiv": vol,
            "active_tier": tier_id,
            "maker_fee_bps": maker_fee_bps,
            "volume_rebate_bps": rebate_bps,
            "tiers": bands,
            "lp_program_note": (
                "High-volume traders share rebate tiers with LP fee waterfall — see GET /v1/liquidity/program."
            ),
        }
    )
    return out


def _latest_block() -> dict[str, Any]:
    rpc = (os.environ.get("GALLEON_RPC") or GALLEON_RPC_DEFAULT).strip()
    try:
        block = rpc_call(rpc, "eth_getBlockByNumber", ["latest", False])
        if isinstance(block, dict):
            num_hex = block.get("number") or "0x0"
            ts_hex = block.get("timestamp") or "0x0"
            return {
                "ok": True,
                "rpc": rpc,
                "block_number": int(num_hex, 16),
                "timestamp": int(ts_hex, 16),
            }
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "rpc": rpc, "error": str(err)[:200]}
    return {"ok": False, "rpc": rpc, "error": "no block result"}


def financing_rate() -> dict[str, Any]:
    block = _latest_block()
    now = time.time()
    ts = block.get("timestamp") if block.get("ok") else None
    anchor = float(ts) if ts else now
    periods = math.floor(anchor / SETTLEMENT_INTERVAL_SECS)
    next_settlement = (periods + 1) * SETTLEMENT_INTERVAL_SECS
    block_num = int(block.get("block_number") or 0)
    vol_seed = (block_num % 97) / 97.0 if block_num else (anchor % 3600) / 3600.0
    if vol_seed < 0.33:
        regime = "calm"
        rate_bps = 2
    elif vol_seed < 0.66:
        regime = "neutral"
        rate_bps = 8
    else:
        regime = "stressed"
        rate_bps = 18
    sign = 1 if (block_num % 2 == 0) else -1
    signed_bps = sign * rate_bps
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_trading_financing",
            "funding_model": "mock_perpetual_rehearsal",
            "rate_bps": signed_bps,
            "rate_abs_bps": rate_bps,
            "direction": "longs_pay" if signed_bps > 0 else "shorts_pay",
            "regime": regime,
            "volatility_placeholder": round(vol_seed, 4),
            "settlement_interval_secs": SETTLEMENT_INTERVAL_SECS,
            "next_settlement_unix": next_settlement,
            "seconds_to_settlement": max(0.0, next_settlement - now),
            "block_probe": block,
            "requires_on_chain": ["funding index oracle", "settlement contract", "legal review"],
        }
    )
    return out


def _load_leaderboard_rows() -> list[dict[str, Any]]:
    path = _leaderboard_path()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return [r for r in raw if isinstance(r, dict)]
            if isinstance(raw, dict) and isinstance(raw.get("entries"), list):
                return [r for r in raw["entries"] if isinstance(r, dict)]
        except (json.JSONDecodeError, OSError):
            pass
    return [dict(r) for r in _REHEARSAL_LEADERBOARD]


def leaderboard(limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    rows = _load_leaderboard_rows()
    rows.sort(key=lambda r: float(r.get("volume_30d_gtest") or r.get("volume_gtest") or 0), reverse=True)
    ranked: list[dict[str, Any]] = []
    for i, row in enumerate(rows[:limit], start=1):
        ranked.append(
            {
                "rank": i,
                "wallet": row.get("wallet") or row.get("address"),
                "volume_30d_gtest": float(row.get("volume_30d_gtest") or row.get("volume_gtest") or 0),
                "trades": int(row.get("trades") or 0),
            }
        )
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_trading_leaderboard",
            "volume_source": "rehearsal_mock",
            "leaderboard_path": str(_leaderboard_path()),
            "entries": ranked,
        }
    )
    return out


def copy_trading_status(wallet: str | None = None) -> dict[str, Any]:
    follows: list[dict[str, Any]] = []
    if wallet:
        follows = [
            {
                "leader_wallet": "0xa1111111111111111111111111111111111111111",
                "label": "rehearsal-leader-1",
                "allocation_bps": 2500,
                "read_only": True,
            }
        ]
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_copy_trading",
            "copy_execution": "not_shipped",
            "server_auto_copy": False,
            "followed_leaders": follows,
            "wallet": wallet,
            "requires": [
                "legal review for copy trading",
                "smart contracts for leader/follower consent",
                "no server-side key custody",
            ],
        }
    )
    return out


def automation_policy() -> dict[str, Any]:
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_trading_automation",
            "allowed": [
                "client_side_walletconnect_scripts",
                "user_approved_transaction_broadcast_from_browser",
                "read_only_api_polling",
            ],
            "not_allowed": [
                "server_side_private_key_signing",
                "hidden_signing",
                "mev_or_front_running",
                "custody_withdrawals_on_host02_or_host03",
            ],
            "bots_note": (
                "Automation bots must run client-side with explicit user consent via WalletConnect "
                "or injected EIP-1193 wallets. This API never holds keys."
            ),
        }
    )
    return out


def _mock_ohlc_series(symbol: str, bars: int = 120) -> list[dict[str, Any]]:
    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    price = 1.0 + (seed % 1000) / 500.0
    series: list[dict[str, Any]] = []
    t0 = int(time.time()) - bars * 300
    for i in range(bars):
        jitter = ((seed + i * 17) % 50 - 25) / 10_000.0
        o = price
        c = max(0.0 + 1e-4, price * (1.0 + jitter))
        h = max(o, c) * (1.0 + abs(jitter) * 0.5)
        l = min(o, c) * (1.0 - abs(jitter) * 0.5)
        series.append(
            {
                "time": t0 + i * 300,
                "open": round(o, 6),
                "high": round(h, 6),
                "low": round(l, 6),
                "close": round(c, 6),
            }
        )
        price = c
    return series


_DEMO_WALLET_ROLES: tuple[tuple[str, str], ...] = (
    ("deploy_signer", "GALLEON_DEPLOY_ADDRESS"),
    ("protocol_treasury_20pct", "GALLEON_PROTOCOL_TREASURY_ADDRESS"),
    ("lp_rewards_pool_80pct", "GALLEON_LP_REWARDS_POOL_ADDRESS"),
    ("lending_reserve", "GALLEON_LENDING_RESERVE_ADDRESS"),
    ("derivatives_margin", "GALLEON_DERIVATIVES_MARGIN_ADDRESS"),
)

_DEFAULT_DEMO_ADDRESSES: dict[str, str] = {
    "deploy_signer": "0x4E902A26B1ED1B709BEE5c26bF0231f731341160",
    "protocol_treasury_20pct": "0x7232ae2d83F7260eE7191251E982dc2EE920eF5e",
    "lp_rewards_pool_80pct": "0x493111c125E5Ab43A182486C03F3c139a5143eFD",
    "lending_reserve": "0x72706c2fA73CD5c6B5189bFCaA606E856f1F6378",
    "derivatives_margin": "0xE143577cbfDd41e977BC7c8A2447a4Dc51d03AC7",
}


def _env_address(key: str, fallback_role: str) -> str | None:
    raw = (os.environ.get(key) or "").strip()
    if raw:
        return raw
    return _DEFAULT_DEMO_ADDRESSES.get(fallback_role)


def demo_wallets() -> dict[str, Any]:
    """Public demo wallet roles for rehearsal (no private keys)."""
    out = _rehearsal_flags()
    wallets: list[dict[str, Any]] = []
    for role, env_key in _DEMO_WALLET_ROLES:
        addr = _env_address(env_key, role)
        wallets.append({"role": role, "address": addr, "env_key": env_key})
    out.update(
        {
            "service": "galleon_demo_wallets",
            "wallets": wallets,
            "note": "Rehearsal roles only. Private keys stay on operator laptop (gitignored).",
        }
    )
    return out


def exchange_features() -> dict[str, Any]:
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_exchange_features",
            "doc": "docs/exchange_feature_matrix.md",
            "implemented_rehearsal": [
                "charts_ohlc_lightweight",
                "volume_tier_rebates",
                "dynamic_financing_stub",
                "leaderboard",
                "copy_trading_read_model",
                "wallet_automation_policy",
                "derivatives_top100_catalog",
                "ranking_changelog",
                "order_book_mock",
                "ticker_24h_mock",
                "order_types_policy",
                "walletconnect_client_trading",
            ],
            "not_shipped": [
                "live_order_matching",
                "server_side_signing",
                "copy_trade_execution",
                "on_chain_funding_settlement",
                "official_tradingview_widget_license",
            ],
            "trading_halted": False,
        }
    )
    return out


def order_types_policy() -> dict[str, Any]:
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_order_types",
            "supported_ui": ["market", "limit", "stop_limit"],
            "execution": "client_simulated_or_wallet_signed",
            "server_broadcast": False,
            "brackets_tp_sl": {"ui": True, "on_chain": False, "not_shipped": True},
        }
    )
    return out


def _mid_price(symbol: str) -> float:
    from sentinel_stack.onchain_market import spot_mid

    px, meta = spot_mid(symbol)
    if px > 0 and meta.get("source") != "mock_rehearsal":
        return px
    series = _mock_ohlc_series(symbol, bars=2)
    return float(series[-1]["close"]) if series else 1.0


def order_book(symbol: str | None = None, depth: int = 12) -> dict[str, Any]:
    sym = (symbol or os.environ.get("TRADING_DEFAULT_SYMBOL") or "gTEST-wiKAS").strip()
    from sentinel_stack.onchain_market import spot_mid

    mid, meta = spot_mid(sym)
    if mid <= 0:
        mid = _mid_price(sym)
        meta = {"source": "mock_rehearsal"}
    bids: list[dict[str, Any]] = []
    asks: list[dict[str, Any]] = []
    depth = max(4, min(int(depth), 24))
    for i in range(depth):
        spread = 0.0015 * (i + 1)
        bids.append({"price": round(mid * (1.0 - spread), 8), "size": round(500.0 / (i + 1), 4)})
        asks.append({"price": round(mid * (1.0 + spread), 8), "size": round(500.0 / (i + 1), 4)})
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_order_book",
            "symbol": sym,
            "mid_price": round(mid, 8),
            "source": meta.get("source"),
            "price_meta": meta,
            "bids": bids,
            "asks": asks,
        }
    )
    return out


def ticker_24h(symbol: str | None = None) -> dict[str, Any]:
    sym = (symbol or os.environ.get("TRADING_DEFAULT_SYMBOL") or "gTEST-wiKAS").strip()
    from sentinel_stack.onchain_market import ohlc_series

    series, meta = ohlc_series(sym, bars=48)
    if not series:
        series = _mock_ohlc_series(sym, bars=48)
        meta = {"source": "mock_rehearsal_series"}
    closes = [float(b["close"]) for b in series]
    highs = [float(b["high"]) for b in series]
    lows = [float(b["low"]) for b in series]
    last = closes[-1]
    open_ = closes[0]
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_ticker",
            "symbol": sym,
            "last": round(last, 6),
            "open_24h": round(open_, 6),
            "high_24h": round(max(highs), 6),
            "low_24h": round(min(lows), 6),
            "change_pct_24h": round((last - open_) / open_ * 100.0, 4) if open_ else 0.0,
            "volume_24h_proxy": round(
                sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))) * 1_000, 4
            ),
            "source": meta.get("source"),
            "market_meta": meta,
        }
    )
    return out


def console_config(symbol: str | None = None) -> dict[str, Any]:
    sym = (symbol or os.environ.get("TRADING_DEFAULT_SYMBOL") or "gTEST-wiKAS").strip()
    from sentinel_stack.onchain_market import ohlc_series

    ohlc, ohlc_meta = ohlc_series(sym, bars=int(os.environ.get("TRADING_OHLC_BARS") or "72"))
    if not ohlc:
        ohlc = _mock_ohlc_series(sym)
        ohlc_meta = {"source": "mock_rehearsal_series"}
    out = _rehearsal_flags()
    out.update(
        {
            "service": "galleon_trading_console",
            "default_symbol": sym,
            "chart_library": "lightweight-charts (TradingView OSS)",
            "ohlc_source": ohlc_meta.get("source"),
            "ohlc_meta": ohlc_meta,
            "ohlc": ohlc,
            "analysis": {"rsi_period": 14, "macd": [12, 26, 9], "computed_client_side": True},
            "endpoints": {
                "volume_rewards": "/v1/trading/volume-rewards",
                "financing": "/v1/trading/financing",
                "leaderboard": "/v1/trading/leaderboard",
                "copy_trading": "/v1/trading/copy-trading/status",
                "automation_policy": "/v1/trading/automation-policy",
                "order_book": "/v1/trading/order-book",
                "ticker": "/v1/trading/ticker",
                "order_types": "/v1/trading/order-types",
                "exchange_features": "/v1/trading/exchange-features",
                "demo_wallets": "/v1/trading/demo-wallets",
            },
            "ui_path": "/ui/dex/trading.html",
        }
    )
    return out
