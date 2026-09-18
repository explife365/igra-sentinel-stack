"""Generic EVM safety gate — structural commitment checks (not on-chain ZK)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sentinel_stack.networks import GALLEON_CHAIN_ID

DEFAULT_MIN_HUB_RESERVE_USD = 50_000.0
DEFAULT_MAX_BLOCK_DRIFT = 5


def safety_commitment(tx_hash: str, hub_reserve_usd: float, block_height_drift: int) -> str:
    payload = f"{tx_hash.strip().lower()}:{hub_reserve_usd}:{block_height_drift}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class UniversalEvmSafetyValidator:
    chain_id: int
    minimum_hub_reserve_usd: float = DEFAULT_MIN_HUB_RESERVE_USD
    maximum_block_drift: int = DEFAULT_MAX_BLOCK_DRIFT
    circuit_breaker_tripped: bool = False
    trip_reason: str | None = None
    trip_tx_hash: str | None = None

    def verify_transaction_safety(
        self,
        tx_hash: str,
        public_inputs: dict[str, Any],
        commitment_token: str,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        tx = (tx_hash or "").strip()

        if self.circuit_breaker_tripped:
            return self._result(
                allowed=False,
                tx_hash=tx,
                reasons=[f"circuit_breaker_open:{self.trip_reason or 'unknown'}"],
                public_inputs=public_inputs,
            )

        reserve = float(public_inputs.get("target_hub_reserve_usd", 0.0))
        drift = int(public_inputs.get("block_height_drift", 0))

        if reserve < self.minimum_hub_reserve_usd:
            reasons.append(
                f"hub_liquidity_below_floor:${reserve:,.2f}<{self.minimum_hub_reserve_usd:,.2f}"
            )
            self._trip(tx, "HUB_LIQUIDITY_DRAIN")

        if drift > self.maximum_block_drift:
            reasons.append(f"block_height_drift:{drift}>{self.maximum_block_drift}")
            self._trip(tx, "BYZANTINE_NODE_DESYNC")

        expected = safety_commitment(tx, reserve, drift)
        token = (commitment_token or "").strip().lower()
        if expected != token:
            reasons.append("commitment_token_mismatch")

        return self._result(
            allowed=len(reasons) == 0,
            tx_hash=tx,
            reasons=reasons,
            public_inputs=public_inputs,
            commitment_expected=expected,
        )

    def _trip(self, tx_hash: str, reason: str) -> None:
        self.circuit_breaker_tripped = True
        self.trip_reason = reason
        self.trip_tx_hash = tx_hash or None

    def _result(
        self,
        *,
        allowed: bool,
        tx_hash: str,
        reasons: list[str],
        public_inputs: dict[str, Any],
        commitment_expected: str | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "not_on_chain_zk": True,
            "not_consensus": True,
            "allowed": allowed,
            "chain_id": self.chain_id,
            "tx_hash": tx_hash or None,
            "reasons": reasons,
            "circuit_breaker_tripped": self.circuit_breaker_tripped,
            "trip_reason": self.trip_reason,
            "public_inputs": public_inputs,
            "commitment_expected": commitment_expected,
            "minimum_hub_reserve_usd": self.minimum_hub_reserve_usd,
            "maximum_block_drift": self.maximum_block_drift,
        }


def validate_safety_payload(body: dict[str, Any]) -> dict[str, Any]:
    chain_id = int(body.get("chain_id") or GALLEON_CHAIN_ID)
    validator = UniversalEvmSafetyValidator(
        chain_id=chain_id,
        minimum_hub_reserve_usd=float(
            body.get("minimum_hub_reserve_usd") or DEFAULT_MIN_HUB_RESERVE_USD
        ),
        maximum_block_drift=int(body.get("maximum_block_drift") or DEFAULT_MAX_BLOCK_DRIFT),
    )
    if body.get("circuit_breaker_tripped"):
        validator.circuit_breaker_tripped = True
        validator.trip_reason = str(body.get("trip_reason") or "PRESET")

    public_inputs = body.get("public_inputs") or {}
    if not isinstance(public_inputs, dict):
        public_inputs = {}

    return validator.verify_transaction_safety(
        tx_hash=str(body.get("tx_hash") or body.get("transaction_hash") or ""),
        public_inputs=public_inputs,
        commitment_token=str(body.get("commitment_token") or body.get("zk_proof_token") or ""),
    )
