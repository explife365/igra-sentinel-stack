"""On-chain Galleon pool quotes for sentinel trading console (no frontier examples path)."""

from __future__ import annotations

import os
import time
from typing import Any

from sentinel_stack.rpc import rpc_call

GALLEON_RPC_DEFAULT = "https://galleon-testnet.igralabs.com:8545"
SELECTOR_GET_RESERVES = "0x0902f1ac"
GTEST_DECIMALS = 18
WIKAS_DECIMALS = 18


def _rpc() -> str:
    return (os.environ.get("GALLEON_RPC") or GALLEON_RPC_DEFAULT).strip()


def _pool() -> str | None:
    return (os.environ.get("GALLEON_FEE_POOL") or os.environ.get("GALLEON_MINI_POOL") or "").strip() or None


def _decode_uint256(hex_result: str) -> int:
    raw = hex_result.strip().removeprefix("0x")
    return int(raw or "0", 16)


def _block_hex(number: int) -> str:
    return hex(max(0, int(number)))


def _parse_legs(symbol: str) -> tuple[str, str]:
    s = symbol.strip()
    for sep in ("-", "/", "_"):
        if sep in s:
            parts = [p for p in s.split(sep) if p]
            if len(parts) >= 2:
                return parts[0], parts[1]
    return "gTEST", "wiKAS"


def _eth_call(to: str, data: str, block: str = "latest") -> str:
    result = rpc_call(_rpc(), "eth_call", [{"to": to, "data": data}, block])
    if not isinstance(result, str):
        raise RuntimeError("eth_call failed")
    return result


def _reserves(pool: str, block: str = "latest") -> tuple[int, int]:
    raw = _eth_call(pool, SELECTOR_GET_RESERVES, block)
    body = raw.removeprefix("0x")
    if len(body) < 128:
        raise RuntimeError("short reserves")
    return _decode_uint256("0x" + body[:64]), _decode_uint256("0x" + body[64:128])


def _price_gtest_to_wikas(r0: int, r1: int) -> float:
    h0 = r0 / (10**GTEST_DECIMALS)
    h1 = r1 / (10**WIKAS_DECIMALS)
    if h0 <= 0:
        return 0.0
    return h1 / h0


def _latest_block() -> int:
    hex_num = rpc_call(_rpc(), "eth_blockNumber", [])
    return int(hex_num, 16)


def _block_ts(block_number: int) -> int:
    result = rpc_call(_rpc(), "eth_getBlockByNumber", [_block_hex(block_number), False])
    if not isinstance(result, dict):
        return int(time.time())
    ts = result.get("timestamp") or "0x0"
    return int(ts, 16) if str(ts).startswith("0x") else int(ts or 0)


def spot_mid(symbol: str) -> tuple[float, dict[str, Any]]:
    pool = _pool()
    meta: dict[str, Any] = {"source": "mock_rehearsal"}
    if not pool:
        return 0.0, meta
    sell, buy = _parse_legs(symbol)
    if sell not in ("gTEST",) or buy not in ("wiKAS",):
        meta["note"] = "sentinel on-chain feed supports gTEST-wiKAS fee pool only"
        return 0.0, meta
    try:
        r0, r1 = _reserves(pool)
        px = _price_gtest_to_wikas(r0, r1)
        if px > 0:
            return px, {"source": "galleon_pool_reserves", "pool": pool, "rpc": _rpc()}
    except Exception as err:  # noqa: BLE001
        meta["error"] = str(err)[:120]
    return 0.0, meta


def ohlc_series(symbol: str, bars: int = 72) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool = _pool()
    meta: dict[str, Any] = {"source": "mock_rehearsal_series"}
    if not pool:
        return [], meta
    sell, buy = _parse_legs(symbol)
    if sell != "gTEST" or buy != "wiKAS":
        return [], meta
    try:
        latest = _latest_block()
    except Exception:
        return [], meta
    step = max(1, int(os.environ.get("TRADING_OHLC_STEP_BLOCKS") or "60"))
    bars = max(12, min(int(bars), 96))
    nums = [max(0, latest - (bars - 1 - i) * step) for i in range(bars)]
    closes: list[tuple[int, float]] = []
    for bn in nums:
        try:
            r0, r1 = _reserves(pool, _block_hex(bn))
            px = _price_gtest_to_wikas(r0, r1)
            if px > 0:
                closes.append((bn, px))
        except Exception:
            continue
    if len(closes) < 3:
        return [], meta
    series: list[dict[str, Any]] = []
    for i, (bn, close) in enumerate(closes):
        ts = _block_ts(bn)
        open_ = closes[i - 1][1] if i else close
        series.append(
            {
                "time": ts,
                "open": round(open_, 8),
                "high": round(max(open_, close) * 1.0002, 8),
                "low": round(min(open_, close) * 0.9998, 8),
                "close": round(close, 8),
                "block": bn,
            }
        )
    meta = {
        "source": "galleon_pool_reserves_history",
        "pool": pool,
        "rpc": _rpc(),
        "step_blocks": step,
        "bars": len(series),
    }
    return series, meta
