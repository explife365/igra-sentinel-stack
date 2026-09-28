"""Operator changelog overlay for Galleon top-100 ranks 21–100 (derivatives rehearsal)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from sentinel_stack.galleon_top100 import _TOP_100_ROWS

MIN_RANK = 21
MAX_RANK = 100
MAX_SLOTS = 80

ChangeType = Literal["insert", "remove", "replace"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def changelog_path() -> Path:
    override = (os.environ.get("GALLEON_RANK_CHANGELOG_PATH") or "").strip()
    if override:
        return Path(override)
    return _repo_root() / ".local" / "galleon_rank_changelog.json"


def _base_rows() -> list[tuple[int, str, str, str]]:
    return list(_TOP_100_ROWS)


def _rows_to_catalog(rows: list[tuple[int, str, str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": sym,
            "rank": rank,
            "native_of": native,
            "hub": hub,
            "ingress": "catalog_only",
            "tier": 3,
        }
        for rank, sym, native, hub in sorted(rows, key=lambda r: r[0])
    ]


def _validate_rows(rows: list[tuple[int, str, str, str]]) -> None:
    ranks = [r[0] for r in rows]
    if len(ranks) != len(set(ranks)):
        raise ValueError("duplicate ranks in effective top-100 catalog")
    if len(rows) > MAX_SLOTS:
        raise ValueError(f"top-100 catalog exceeds {MAX_SLOTS} slots")
    for rank in ranks:
        if rank < MIN_RANK or rank > MAX_RANK:
            raise ValueError(f"rank {rank} outside {MIN_RANK}–{MAX_RANK}")


def apply_ranking_change(
    rows: list[tuple[int, str, str, str]],
    event: dict[str, Any],
) -> list[tuple[int, str, str, str]]:
    kind = str(event.get("type") or event.get("change") or "").strip().lower()
    if kind not in ("insert", "remove", "replace"):
        raise ValueError(f"unknown ranking change type: {kind!r}")

    rank = int(event["rank"])
    if rank < MIN_RANK or rank > MAX_RANK:
        raise ValueError(f"rank {rank} outside {MIN_RANK}–{MAX_RANK}")

    if kind == "insert":
        symbol = str(event["symbol"]).strip()
        native_of = str(event.get("native_of") or symbol.lstrip("wt")).strip()
        hub = str(event.get("hub") or "gTEST").strip()
        bumped: list[tuple[int, str, str, str]] = []
        for r, sym, nat, h in sorted(rows):
            if r < rank:
                bumped.append((r, sym, nat, h))
            elif r >= rank:
                nr = r + 1
                if nr <= MAX_RANK:
                    bumped.append((nr, sym, nat, h))
        bumped.append((rank, symbol, native_of, hub))
        bumped.sort(key=lambda x: x[0])
        by_rank = {r: (sym, nat, h) for r, sym, nat, h in bumped}
        while len(by_rank) > MAX_SLOTS:
            drop = max(by_rank)
            del by_rank[drop]
        out = [(r, sym, nat, h) for r, (sym, nat, h) in sorted(by_rank.items())]
        _validate_rows(out)
        return out

    if kind == "remove":
        out: list[tuple[int, str, str, str]] = []
        for r, sym, nat, h in sorted(rows):
            if r < rank:
                out.append((r, sym, nat, h))
            elif r > rank:
                out.append((r - 1, sym, nat, h))
        _validate_rows(out)
        return out

    symbol = str(event["symbol"]).strip()
    native_of = str(event.get("native_of") or symbol.lstrip("wt")).strip()
    hub = str(event.get("hub") or "gTEST").strip()
    out = []
    replaced = False
    for r, sym, nat, h in rows:
        if r == rank:
            out.append((rank, symbol, native_of, hub))
            replaced = True
        else:
            out.append((r, sym, nat, h))
    if not replaced:
        out.append((rank, symbol, native_of, hub))
        out.sort(key=lambda x: x[0])
    _validate_rows(out)
    return out


def load_changelog_events() -> list[dict[str, Any]]:
    path = changelog_path()
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if isinstance(raw, dict) and "events" in raw:
        events = raw["events"]
    elif isinstance(raw, list):
        events = raw
    else:
        raise ValueError("changelog must be a JSON array or {events: [...]}")
    if not isinstance(events, list):
        raise ValueError("changelog events must be a list")
    return [e for e in events if isinstance(e, dict)]


def effective_top100_rows() -> list[tuple[int, str, str, str]]:
    rows = _base_rows()
    for event in load_changelog_events():
        rows = apply_ranking_change(rows, event)
    return rows


def effective_top100_catalog_entries() -> list[dict[str, Any]]:
    return _rows_to_catalog(effective_top100_rows())


def ranking_changelog_summary(limit: int = 20) -> dict[str, Any]:
    path = changelog_path()
    events = load_changelog_events() if path.is_file() else []
    recent = events[-limit:] if events else []
    return {
        "version": len(events),
        "count": len(events),
        "recent": recent,
        "pending": [] if path.is_file() else [],
        "changelog_path": str(path),
        "changelog_loaded": path.is_file(),
        "operator_note": (
            "Append ranking events to galleon_rank_changelog.json on the integrator host; "
            "no browser POST."
        ),
    }


def ranking_changes_for_status(limit: int = 20) -> dict[str, Any]:
    summary = ranking_changelog_summary(limit=limit)
    if not summary["changelog_loaded"]:
        return {"version": 0, "entries": [], "pending": []}
    return {
        "version": summary["version"],
        "entries": summary["recent"],
        "pending": summary["pending"],
    }
