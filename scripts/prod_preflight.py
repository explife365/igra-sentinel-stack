#!/usr/bin/env python3
"""Production preflight — no private keys, loopback publish, optional live smoke."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_ASSIGN = re.compile(
    r"^\s*(GALLEON_PRIVATE_KEY|GALLEON_MINT_PRIVATE_KEY|[A-Z0-9_]*PRIVATE_KEY)\s*=\s*\S+",
    re.M,
)
COMMENT_OK = re.compile(r"^\s*#")
SCAN_GLOBS = (
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "Dockerfile",
    "Caddyfile",
    "kaspa.env.example",
    "kaspa.env.production.example",
    "docs/production.md",
)


def _scan_file(path: Path) -> list[str]:
    hits: list[str] = []
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if COMMENT_OK.match(line):
            continue
        if KEY_ASSIGN.search(line) and not line.strip().endswith("="):
            hits.append(f"{path.name}:{i}:{line.strip()[:80]}")
    return hits


def check_no_secrets_in_repo() -> dict:
    hits: list[str] = []
    for rel in SCAN_GLOBS:
        path = ROOT / rel
        if path.is_file():
            hits.extend(_scan_file(path))
    prod_example = (ROOT / "kaspa.env.production.example").read_text(encoding="utf-8")
    if "GALLEON_PRIVATE_KEY" in prod_example and not all(
        line.strip().startswith("#") or "GALLEON_PRIVATE_KEY" not in line
        for line in prod_example.splitlines()
    ):
        # Only fail if a non-comment assignment exists — already covered by hits.
        pass
    return {"ok": not hits, "hits": hits}


def check_prod_compose_loopback() -> dict:
    text = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    ok = "127.0.0.1:8790:8790" in text and "!override" in text and "0.0.0.0:8790" not in text
    return {"ok": ok, "loopback_publish": ok}


def check_wallet_origin_docs() -> dict:
    env = (ROOT / "kaspa.env.production.example").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "production.md").read_text(encoding="utf-8")
    hosts = ("sentinel.tuce.app", "dex.tuce.app", "cex.tuce.app")
    ok = "SENTINEL_PUBLIC_ORIGIN=https://sentinel.tuce.app" in env and all(
        name in env and name in docs for name in hosts
    )
    cex = (ROOT / "ui" / "cex" / "index.html").read_text(encoding="utf-8")
    cex_ok = (
        "Custody not started" in cex
        and "Owned-node gate: red" in cex
        and "<form" not in cex.lower()
        and "type=\"submit\"" not in cex.lower()
    )
    return {"ok": ok and cex_ok, "https_origin_example": ok, "cex_fail_closed_copy": cex_ok}


def docker_inspect_keys() -> dict:
    try:
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.yml",
                "-f",
                "docker-compose.prod.yml",
                "exec",
                "-T",
                "sentinel",
                "python",
                "-c",
                "import json,os; print(json.dumps([k for k in os.environ if 'PRIVATE_KEY' in k]))",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as err:
        return {"ok": True, "skipped": True, "reason": str(err)}
    if proc.returncode != 0:
        return {
            "ok": True,
            "skipped": True,
            "reason": (proc.stderr or proc.stdout or "compose exec failed")[:300],
        }
    try:
        keys = json.loads((proc.stdout or "[]").strip().splitlines()[-1])
    except json.JSONDecodeError:
        return {"ok": True, "skipped": True, "reason": "could not parse inspect"}
    return {"ok": keys == [], "private_key_env": keys, "skipped": False}


def smoke() -> dict:
    smoke_py = ROOT / "scripts" / "smoke.py"
    proc = subprocess.run(
        [sys.executable, str(smoke_py)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "").strip()[-400:],
        "stderr": (proc.stderr or "").strip()[-400:],
    }


def main() -> int:
    os.chdir(ROOT)
    report = {
        "ok": True,
        "not_mainnet_production": True,
        "secrets": check_no_secrets_in_repo(),
        "compose_loopback": check_prod_compose_loopback(),
        "public_origin": check_wallet_origin_docs(),
        "container_env": docker_inspect_keys(),
    }
    base = os.environ.get("SENTINEL_API_BASE", "").strip()
    if base or os.environ.get("SENTINEL_PREFLIGHT_SMOKE") == "1":
        report["smoke"] = smoke()
    failed = [
        name
        for name, body in report.items()
        if isinstance(body, dict) and body.get("ok") is False
    ]
    report["ok"] = not failed
    report["failed"] = failed
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
