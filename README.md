# Igra Sentinel Stack

Chain safety gates and dual-network probes for **Igra EVM** — Galleon testnet rehearsal (chain `38836`) plus read-only Igra mainnet health (chain `38833`).

This is a **slim, standalone** companion to [kaspa-frontier-engine](https://github.com/explife365/kaspa-frontier-engine). Swap routing, hub deploys, and the full DEX terminal remain in the frontier repo.

## What this is

| Layer | Shipped here |
|-------|----------------|
| Network probes | Galleon + Igra mainnet RPC reachability, read-only detection |
| Safety gates | SHA-256 commitment checks (`POST /v1/evm/safety-verify`) — **not** on-chain ZK |
| Bridge verify | KatBridge KIP-21 structural checks (`POST /v1/funding/bridge-verify`) |
| Wallet connect UI | EIP-6963 + WalletConnect on Galleon (`/ui/dex`) |
| Client hooks | Fail-closed CLI before broadcast (`python -m sentinel_stack.hooks`) |

## What this is not

- **Not** an Igra Labs partnership, grant, or endorsement (`not_partnership: true` on all catalog endpoints).
- **Not** mainnet production sentinel — no FeePool/hub deploy on chain `38833` in this repo.
- **Not** consensus or SilverScript ZK — commitments are off-chain SHA-256 only.
- **Not** StrataX / Guard Sentinel — that is a separate product.

## Quick start

```bash
cd igra-sentinel-stack
cp kaspa.env.example kaspa.env
# optional: WALLETCONNECT_PROJECT_ID=... in kaspa.env

python -m sentinel_stack.api
# Dashboard  http://127.0.0.1:8790/ui
# Status     http://127.0.0.1:8790/v1/sentinel/status
# Wallet UI  http://127.0.0.1:8790/ui/dex
```

### Smoke test (server running)

```bash
python scripts/smoke.py
```

### Client hook

```bash
python -m sentinel_stack.hooks --verify-tx --gas-gwei 50
```

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/v1/sentinel/status` | Dual-network probes + blockers |
| GET | `/v1/igra/ecosystem` | Compatibility catalog (no partnership claims) |
| GET | `/v1/networks` | Galleon + mainnet metadata |
| GET | `/v1/dex/wallet/connect-config` | WalletConnect / chain params |
| POST | `/v1/evm/safety-verify` | Universal EVM safety gate |
| POST | `/v1/funding/bridge-verify` | KatBridge intent validation |

## Docker

```bash
docker compose up --build
```

Binds `8790` by default.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Upstream

Full integrator, Galleon DEX router, and liquidity tooling:

**https://github.com/explife365/kaspa-frontier-engine**

## License

As-is rehearsal stack — see repository license when published.
