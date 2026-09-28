"""Galleon LP incentive program — week/month epochs, fee split, optional renewal.

Liquidity provision incentives only. NOT MEV, NOT front-running, NOT mainnet yield.
Mock in-memory state; no on-chain deploy in this module.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

ROOT_DISCLAIMER = (
    "Galleon testnet rehearsal only. Not mainnet. Not consensus. "
    "Not CEX custody. LP incentives — not transaction-order exploitation."
)

WEEK_SECS = 7 * 86_400
MONTH_SECS = 30 * 86_400


class EpochDuration(str, Enum):
    WEEK = "week"
    MONTH = "month"


def _duration_secs(duration: EpochDuration) -> int:
    return WEEK_SECS if duration == EpochDuration.WEEK else MONTH_SECS


@dataclass
class LiquidityEnrollment:
    participant_id: str
    duration: EpochDuration
    auto_renew: bool
    liquidity_gtest_equiv: float
    enrolled_at_epoch_id: str


@dataclass
class LiquidityEpoch:
    epoch_id: str
    duration: EpochDuration
    started_at: float
    ends_at: float
    total_fees_gtest_equiv: float = 0.0
    enrollments: list[LiquidityEnrollment] = field(default_factory=list)


def fee_split_bps() -> tuple[int, int]:
    """Return (contributor_bps, protocol_bps). Default 8000 / 2000."""
    contrib = int(os.environ.get("LIQUIDITY_PROGRAM_CONTRIBUTOR_BPS", "8000"))
    protocol = int(os.environ.get("LIQUIDITY_PROGRAM_PROTOCOL_BPS", "2000"))
    if contrib + protocol != 10_000:
        raise ValueError("contributor_bps + protocol_bps must equal 10000")
    if contrib < 0 or protocol < 0:
        raise ValueError("bps must be non-negative")
    return contrib, protocol


def split_fees(total_gtest_equiv: float) -> dict[str, float]:
    if total_gtest_equiv < 0:
        raise ValueError("total fees must be non-negative")
    contrib_bps, protocol_bps = fee_split_bps()
    contributors = total_gtest_equiv * contrib_bps / 10_000
    protocol = total_gtest_equiv * protocol_bps / 10_000
    return {
        "total_gtest_equiv": total_gtest_equiv,
        "contributors_gtest_equiv": contributors,
        "protocol_gtest_equiv": protocol,
        "contributor_bps": contrib_bps,
        "protocol_bps": protocol_bps,
    }


def _total_enrolled_liquidity(epoch: LiquidityEpoch) -> float:
    return sum(max(0.0, e.liquidity_gtest_equiv) for e in epoch.enrollments)


def contributor_share(
    epoch: LiquidityEpoch,
    participant_id: str,
    *,
    fees: dict[str, float] | None = None,
) -> dict[str, Any]:
    fees = fees or split_fees(epoch.total_fees_gtest_equiv)
    pool = fees["contributors_gtest_equiv"]
    mine = sum(
        e.liquidity_gtest_equiv
        for e in epoch.enrollments
        if e.participant_id == participant_id and e.liquidity_gtest_equiv > 0
    )
    total = _total_enrolled_liquidity(epoch)
    if total <= 0 or mine <= 0:
        return {
            "participant_id": participant_id,
            "share_gtest_equiv": 0.0,
            "share_of_contributor_pool": 0.0,
            "liquidity_gtest_equiv": mine,
        }
    share = pool * (mine / total)
    return {
        "participant_id": participant_id,
        "share_gtest_equiv": share,
        "share_of_contributor_pool": mine / total,
        "liquidity_gtest_equiv": mine,
    }


def renew_enrollments(
    ended_epoch: LiquidityEpoch,
    next_epoch_id: str,
) -> list[LiquidityEnrollment]:
    """Copy enrollments with auto_renew into the next epoch id."""
    renewed: list[LiquidityEnrollment] = []
    for e in ended_epoch.enrollments:
        if not e.auto_renew:
            continue
        renewed.append(
            LiquidityEnrollment(
                participant_id=e.participant_id,
                duration=e.duration,
                auto_renew=e.auto_renew,
                liquidity_gtest_equiv=e.liquidity_gtest_equiv,
                enrolled_at_epoch_id=next_epoch_id,
            )
        )
    return renewed


def new_epoch(
    duration: EpochDuration,
    *,
    now: float | None = None,
    epoch_id: str | None = None,
) -> LiquidityEpoch:
    now = now if now is not None else time.time()
    eid = epoch_id or f"epoch-{duration.value}-{uuid.uuid4().hex[:8]}"
    span = _duration_secs(duration)
    return LiquidityEpoch(
        epoch_id=eid,
        duration=duration,
        started_at=now,
        ends_at=now + span,
        total_fees_gtest_equiv=0.0,
        enrollments=[],
    )


def enroll(
    epoch: LiquidityEpoch,
    participant_id: str,
    liquidity_gtest_equiv: float,
    *,
    auto_renew: bool = False,
) -> LiquidityEnrollment:
    if liquidity_gtest_equiv <= 0:
        raise ValueError("liquidity_gtest_equiv must be positive")
    entry = LiquidityEnrollment(
        participant_id=participant_id,
        duration=epoch.duration,
        auto_renew=auto_renew,
        liquidity_gtest_equiv=liquidity_gtest_equiv,
        enrolled_at_epoch_id=epoch.epoch_id,
    )
    epoch.enrollments.append(entry)
    return entry


def _env_address(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _treasury_config() -> dict[str, Any]:
    contrib_vault = _env_address(
        "LIQUIDITY_PROGRAM_CONTRIBUTORS_VAULT",
        "GALLEON_LP_REWARDS_POOL_ADDRESS",
    )
    protocol = _env_address(
        "LIQUIDITY_PROGRAM_PROTOCOL_TREASURY",
        "GALLEON_PROTOCOL_TREASURY_ADDRESS",
    )
    return {
        "contributors_vault": contrib_vault or None,
        "protocol_treasury": protocol or None,
        "configured": bool(contrib_vault and protocol),
    }


# In-process mock state for integrator GET (reset on process restart).
_MOCK_STATE: dict[str, Any] = {
    "epochs": [],
    "closed_epochs": [],
}


def _seed_mock_epochs(now: float) -> None:
    if _MOCK_STATE["epochs"]:
        return
    week = new_epoch(EpochDuration.WEEK, now=now, epoch_id="rehearsal-week-1")
    week.total_fees_gtest_equiv = 100.0
    enroll(week, "lp-alpha", 60.0, auto_renew=True)
    enroll(week, "lp-beta", 40.0, auto_renew=False)
    month = new_epoch(EpochDuration.MONTH, now=now, epoch_id="rehearsal-month-1")
    month.total_fees_gtest_equiv = 250.0
    enroll(month, "lp-alpha", 100.0, auto_renew=True)
    _MOCK_STATE["epochs"] = [week, month]


def program_status() -> dict[str, Any]:
    now = time.time()
    _seed_mock_epochs(now)
    contrib_bps, protocol_bps = fee_split_bps()
    epochs_out: list[dict[str, Any]] = []
    for ep in _MOCK_STATE["epochs"]:
        fees = split_fees(ep.total_fees_gtest_equiv)
        epochs_out.append(
            {
                "epoch_id": ep.epoch_id,
                "duration": ep.duration.value,
                "started_at": ep.started_at,
                "ends_at": ep.ends_at,
                "seconds_remaining": max(0.0, ep.ends_at - now),
                "total_fees_gtest_equiv": ep.total_fees_gtest_equiv,
                "fee_split": fees,
                "enrollments": [asdict(e) for e in ep.enrollments],
                "total_liquidity_gtest_equiv": _total_enrolled_liquidity(ep),
            }
        )
    return {
        "ok": True,
        "service": "galleon_liquidity_program",
        "chain_id": 38836,
        "not_mainnet": True,
        "not_consensus": True,
        "not_shipped_on_chain": True,
        "deploy_allowed": False,
        "disclaimer": ROOT_DISCLAIMER,
        "naming": "LP liquidity incentives (not MEV / not front-running)",
        "fee_split_default": {"contributor_bps": contrib_bps, "protocol_bps": protocol_bps},
        "treasury": _treasury_config(),
        "auto_renew_supported": True,
        "epochs": epochs_out,
        "docs_path": "docs/liquidity_rewards_rehearsal.md",
    }


def lending_status() -> dict[str, Any]:
    reserve = _env_address("GALLEON_LENDING_RESERVE_ADDRESS")
    return {
        "ok": True,
        "phase": 2,
        "not_shipped": True,
        "deploy_allowed": False,
        "disclaimer": ROOT_DISCLAIMER,
        "product": "testnet lending scaffold",
        "max_ltv_bps": 6500,
        "liquidation_bonus_bps": 500,
        "allowed_collateral": ["gTEST", "wiKAS", "tUSDC"],
        "lending_reserve": reserve or None,
        "live_probes": False,
        "requires": [
            "collateral oracles",
            "risk engine",
            "legal review",
            "GALLEON_LENDING_RESERVE_ADDRESS or treasury wiring",
        ],
    }


def derivatives_status() -> dict[str, Any]:
    from sentinel_stack.galleon_rank_registry import (
        effective_top100_catalog_entries,
        ranking_changes_for_status,
    )
    from sentinel_stack.galleon_top100 import top100_summary

    margin = _env_address("GALLEON_DERIVATIVES_MARGIN_ADDRESS")
    return {
        "ok": True,
        "phase": 2,
        "not_shipped": True,
        "deploy_allowed": False,
        "disclaimer": ROOT_DISCLAIMER,
        "product": "perpetual derivatives rehearsal",
        "max_leverage": 3,
        "margin_mode": "isolated",
        "margin_account": margin or None,
        "live_trading": False,
        "live_probes": False,
        "top_100": top100_summary(),
        "markets_catalog": effective_top100_catalog_entries(),
        "ranking_changes": ranking_changes_for_status(),
        "markets_note": (
            "Perpetual rehearsal catalog only; ranks 21–100 with operator changelog overlay; "
            "no live perps."
        ),
        "requires": [
            "mark price feed",
            "liquidation engine",
            "leverage caps on-chain",
            "no public-host signing keys",
            "GALLEON_DERIVATIVES_MARGIN_ADDRESS for rehearsal accounting",
        ],
    }
