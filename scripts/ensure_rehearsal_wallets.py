"""Create missing Galleon rehearsal role wallets in kaspa.wallets.local.env (gitignored)."""

from __future__ import annotations

from pathlib import Path

from eth_account import Account

STACK = Path(__file__).resolve().parents[1]
WALLETS_FILE = STACK / "kaspa.wallets.local.env"

ROLES: tuple[tuple[str, str], ...] = (
    ("GALLEON_PROTOCOL_TREASURY", "GALLEON_PROTOCOL_TREASURY_ADDRESS"),
    ("GALLEON_LP_REWARDS_POOL", "GALLEON_LP_REWARDS_POOL_ADDRESS"),
    ("GALLEON_LENDING_RESERVE", "GALLEON_LENDING_RESERVE_ADDRESS"),
    ("GALLEON_DERIVATIVES_MARGIN", "GALLEON_DERIVATIVES_MARGIN_ADDRESS"),
)


def _parse_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    existing = _parse_env(WALLETS_FILE)
    out_lines = [
        "# Galleon TN10 rehearsal role wallets — NEVER commit. Local only; do not scp to VPS.",
        "# Source with kaspa.env: set -a; source kaspa.wallets.local.env; source kaspa.env; set +a",
        "",
    ]
    changed = False
    for priv_key, addr_key in ROLES:
        priv = existing.get(priv_key, "").strip()
        addr = existing.get(addr_key, "").strip()
        if priv and not priv.startswith("0x"):
            priv = "0x" + priv
        if priv:
            derived = Account.from_key(priv).address
            if addr and addr.lower() != derived.lower():
                raise SystemExit(f"{priv_key}: address does not match private key")
            addr = derived
        else:
            acct = Account.create()
            priv = acct.key.hex()
            if not priv.startswith("0x"):
                priv = "0x" + priv
            addr = acct.address
            changed = True
        role_tag = priv_key.removeprefix("GALLEON_").lower()
        out_lines.append(f"# role: {role_tag}")
        out_lines.append(f"{priv_key}={priv}")
        out_lines.append(f"{addr_key}={addr}")
        out_lines.append("")
        print(f"{role_tag}\t{addr_key}\t{addr}")

    if changed or not WALLETS_FILE.exists():
        WALLETS_FILE.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
        print(f"wrote {WALLETS_FILE.name} (changed={changed})")
    else:
        print(f"{WALLETS_FILE.name} unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
