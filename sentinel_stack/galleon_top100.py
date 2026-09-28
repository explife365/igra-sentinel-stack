"""Top-100 market-cap catalog (ranks 21–100) — metadata + lazy pool tier 3."""

from __future__ import annotations

from typing import Any

# (rank, symbol, native_of, hub)
_TOP_100_ROWS: tuple[tuple[int, str, str, str], ...] = (
    (21, "wXLM", "XLM", "gTEST"),
    (22, "wNEAR", "NEAR", "gTEST"),
    (23, "wAPT", "APT", "gTEST"),
    (24, "wICP", "ICP", "gTEST"),
    (25, "wFIL", "FIL", "gTEST"),
    (26, "wHBAR", "HBAR", "gTEST"),
    (27, "wCRO", "CRO", "gTEST"),
    (28, "wVET", "VET", "gTEST"),
    (29, "wMKR", "MKR", "gTEST"),
    (30, "wAAVE", "AAVE", "gTEST"),
    (31, "wALGO", "ALGO", "gTEST"),
    (32, "wQNT", "QNT", "gTEST"),
    (33, "wGRT", "GRT", "gTEST"),
    (34, "wRNDR", "RNDR", "gTEST"),
    (35, "wINJ", "INJ", "gTEST"),
    (36, "wIMX", "IMX", "gTEST"),
    (37, "wRUNE", "RUNE", "gTEST"),
    (38, "wFTM", "FTM", "gTEST"),
    (39, "wSEI", "SEI", "gTEST"),
    (40, "wARB", "ARB", "gTEST"),
    (41, "wOP", "OP", "gTEST"),
    (42, "wSTX", "STX", "gTEST"),
    (43, "wTIA", "TIA", "gTEST"),
    (44, "wLDO", "LDO", "gTEST"),
    (45, "wSUI", "SUI", "gTEST"),
    (46, "wFET", "FET", "gTEST"),
    (47, "wJASMY", "JASMY", "gTEST"),
    (48, "wGALA", "GALA", "gTEST"),
    (49, "wSAND", "SAND", "gTEST"),
    (50, "wMANA", "MANA", "gTEST"),
    (51, "wAXS", "AXS", "gTEST"),
    (52, "wTHETA", "THETA", "gTEST"),
    (53, "wEGLD", "EGLD", "gTEST"),
    (54, "wFLOW", "FLOW", "gTEST"),
    (55, "wKCS", "KCS", "gTEST"),
    (56, "wXTZ", "XTZ", "gTEST"),
    (57, "wASTR", "ASTR", "gTEST"),
    (58, "wIOTA", "IOTA", "gTEST"),
    (59, "wNEO", "NEO", "gTEST"),
    (60, "wZEC", "ZEC", "gTEST"),
    (61, "wDASH", "DASH", "gTEST"),
    (62, "wEOS", "EOS", "gTEST"),
    (63, "wHNT", "HNT", "gTEST"),
    (64, "wENJ", "ENJ", "gTEST"),
    (65, "wCHZ", "CHZ", "gTEST"),
    (66, "wBAT", "BAT", "gTEST"),
    (67, "wZIL", "ZIL", "gTEST"),
    (68, "wCOMP", "COMP", "gTEST"),
    (69, "wSNX", "SNX", "gTEST"),
    (70, "wCRV", "CRV", "gTEST"),
    (71, "w1INCH", "1INCH", "gTEST"),
    (72, "wDYDX", "DYDX", "gTEST"),
    (73, "wGMX", "GMX", "gTEST"),
    (74, "wCAKE", "CAKE", "gTEST"),
    (75, "wKAVA", "KAVA", "gTEST"),
    (76, "wROSE", "ROSE", "gTEST"),
    (77, "wMINA", "MINA", "gTEST"),
    (78, "wCFX", "CFX", "gTEST"),
    (79, "wKLAY", "KLAY", "gTEST"),
    (80, "wOSMO", "OSMO", "gTEST"),
    (81, "wBLUR", "BLUR", "gTEST"),
    (82, "wPEPE", "PEPE", "gTEST"),
    (83, "wBONK", "BONK", "gTEST"),
    (84, "wWIF", "WIF", "gTEST"),
    (85, "wJUP", "JUP", "gTEST"),
    (86, "wPYTH", "PYTH", "gTEST"),
    (87, "wSTRK", "STRK", "gTEST"),
    (88, "wMANTA", "MANTA", "gTEST"),
    (89, "wWLD", "WLD", "gTEST"),
    (90, "wORDI", "ORDI", "gTEST"),
    (91, "wTWT", "TWT", "gTEST"),
    (92, "wFXS", "FXS", "gTEST"),
    (93, "wLRC", "LRC", "gTEST"),
    (94, "wANKR", "ANKR", "gTEST"),
    (95, "wCELO", "CELO", "gTEST"),
    (96, "wONE", "ONE", "gTEST"),
    (97, "wGLMR", "GLMR", "gTEST"),
    (98, "tDAI", "DAI", "tUSDC"),
    (99, "tFDUSD", "FDUSD", "tUSDC"),
    (100, "tTUSD", "TUSD", "tUSDC"),
)


def top100_catalog_entries() -> list[dict[str, Any]]:
    """Catalog rows for ranks 21–100 (base snapshot; prefer effective_top100_catalog_entries)."""
    from sentinel_stack.galleon_rank_registry import effective_top100_catalog_entries

    return effective_top100_catalog_entries()


def top100_summary() -> dict[str, Any]:
    entries = top100_catalog_entries()
    return {
        "count": len(entries),
        "rank_range": [entries[0]["rank"], entries[-1]["rank"]] if entries else [21, 100],
        "hubs": {
            "gTEST": sum(1 for e in entries if e["hub"] == "gTEST"),
            "tUSDC": sum(1 for e in entries if e["hub"] == "tUSDC"),
        },
        "lazy_tier": 3,
        "deploy_trigger": "volume threshold via /v1/dex/lazy-pools after register",
        "ranking_overlay": True,
    }
