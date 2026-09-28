# Exchange feature matrix (Galleon rehearsal)

Chain **38836** testnet only. Not mainnet. Not consensus. Not CEX custody on public hosts.

| Feature | Binance / Coinbase / dYdX pattern | Rehearsal status | API / UI |
|--------|-----------------------------------|------------------|----------|
| Candlestick chart | Standard | Mock OHLC + lightweight-charts | `/ui/dex/trading.html`, `/v1/trading/console-config` |
| Order book | Depth ladder | Mock depth | `/v1/trading/order-book` |
| 24h ticker | High/low/volume | Mock | `/v1/trading/ticker` |
| Market / limit / stop-limit | Order types | Policy + UI; no server match | `/v1/trading/order-types` |
| Volume rebates | VIP tiers | Live config | `/v1/trading/volume-rewards` |
| Funding / financing | Perp funding | Stub from block + regime | `/v1/trading/financing` |
| Leaderboard | Ranked traders | File or mock | `/v1/trading/leaderboard` |
| Copy trading | Follow leaders | Read-only; execution not shipped | `/v1/trading/copy-trading/status` |
| Wallet automation | API / bots | Client WC only | `/v1/trading/automation-policy` |
| Derivatives catalog | Perp markets | Top 100 ranks 21–100 | `/v1/derivatives/status` |
| Rank changes | Listings | Changelog file on operator host | `/v1/derivatives/ranking-changelog` |
| TP/SL brackets | Advanced orders | UI placeholder; not on-chain | `order_types.brackets_tp_sl` |
| Kill switch | Halt trading | `trading_halted: false` | `/v1/trading/exchange-features` |
| Demo wallets | Treasury roles | Public addresses only | `/v1/trading/demo-wallets` |

Demo wallet roles map to env `GALLEON_*_ADDRESS` on the operator laptop; private keys are never on host02/host03.

## Re-run exchange rehearsal

From **kaspa-frontier-engine** (integrator parity):

```bash
python scripts/galleon_demo_rehearsal.py
```

Default base is `https://dex.tuce.app` (this sentinel stack on host02). Expect **14/14** with `live_trading=false`.

**Deploy:** copy this repo to `/opt/igra-sentinel-stack` on host02 and `systemctl restart igra-sentinel`. Integrator mirror lives in `kaspa-frontier-engine/examples/`.
