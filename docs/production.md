# Public Galleon Sentinel

Honest label: **public Galleon rehearsal (chain 38836)**. Not an Igra partnership. Not Igra mainnet (38833) production. Not consensus. Not CEX custody.

Swap broadcast and hub deploys are not shipped on this host. This box never holds `GALLEON_PRIVATE_KEY` or mint keys.

## Hostnames

| Host | Role |
|------|------|
| `sentinel.tuce.app` | Primary front door. Status, ecosystem, networks, rehearsal banners. Canonical `SENTINEL_PUBLIC_ORIGIN`. |
| `dex.tuce.app` | DEX / Galleon testnet rehearsal, chain 38836. |
| `cex.tuce.app` | Fail-closed CEX rehearsal. Custody is not started. No orders, withdrawals, or broadcasts. |

The request `Host` is accepted for origin and WalletConnect metadata only when it is exactly one of those three names. Any other `Host` is ignored. When a single fallback is required, set:

`SENTINEL_PUBLIC_ORIGIN=https://sentinel.tuce.app`

Active profile stays `galleon-testnet`. This host advertises `deploy_allowed: false` for chain 38836 and chain 38833. Chain 38836 may stay reachable.

## Architecture

```
Internet --443--> TLS proxy --> 127.0.0.1:8790 --> sentinel
```

Port `8790` is loopback-only. Do not publish it on the public NIC. Do not proxy `/` to kaspad. Do not publish `16210` or `18210`.

On host02, nginx already owns ports 80 and 443 for `host02.tuce.app` and `sat.tuce.app`. Add server blocks for the three Sentinel names only. Do not replace those existing certificates. Reload nginx only after `nginx -t` succeeds.

`Caddyfile` is for a host where nothing else owns 443. Do not start it beside nginx.

The systemd unit is the host02 process. `docker-compose.prod.yml` resets the published port to `127.0.0.1:8790` with `!override`. Do not start the compose stack unless that overlay is the one in use. Do not start it in a way that also publishes `0.0.0.0:8790`.

## Env

```bash
sudo mkdir -p /etc/igra-sentinel
sudo cp kaspa.env.production.example /etc/igra-sentinel/kaspa.env
sudo chmod 600 /etc/igra-sentinel/kaspa.env
```

Set `SENTINEL_PUBLIC_ORIGIN=https://sentinel.tuce.app`. Leave `WALLETCONNECT_PROJECT_ID` unset until a real id exists. Do not invent one.

**Forbidden in this file:** `GALLEON_PRIVATE_KEY`, `GALLEON_MINT_PRIVATE_KEY`, any `*_PRIVATE_KEY`.

`SENTINEL_TRUST_PROXY=1` belongs behind the TLS proxy so the POST limiter keys on `X-Forwarded-For`.

## Rate limits

`POST /v1/evm/safety-verify` and `POST /v1/funding/bridge-verify` share a per-client sliding window:

- `SENTINEL_POST_RATE_LIMIT` (default 30)
- `SENTINEL_POST_RATE_WINDOW` (default 60 seconds)

## What this host must not do

| Do not | Why |
|--------|-----|
| Store `GALLEON_PRIVATE_KEY` | Public sentinel is not an operator wallet |
| Start CEX custody (`:8787`, outbox, withdrawals, broadcast) | The CEX surface is fail-closed |
| Deploy from this host on chain 38836 or 38833 | `deploy_allowed: false` on both profiles |
| Claim an Igra partnership, consensus, or mainnet production | Catalog and pages refuse that |
| Open `:8790`, `:16210`, or `:18210` on `0.0.0.0` | The app and kaspad RPC stay on loopback |

## Checks

```bash
python scripts/smoke.py
python scripts/prod_preflight.py
```

Smoke defaults to `http://127.0.0.1:8790` and sends the three public `Host` values. Against HTTPS:

```bash
export SENTINEL_API_BASE=https://sentinel.tuce.app
python scripts/smoke.py
```

Browser checks:

- `https://sentinel.tuce.app/` — status, banners, links to DEX and CEX
- `https://dex.tuce.app/` — chain 38836 rehearsal, no broadcast control
- `https://cex.tuce.app/` — owned-node gate red, custody not started
- `https://sentinel.tuce.app/v1/sentinel/status` — `not_partnership`, `not_consensus`, `not_mainnet_production`
