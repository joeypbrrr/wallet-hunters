# Wallet Hunters / The Astral Vault

A separate, public, read-only Solana research observatory. **No trading, wallet connection, private keys, execution or external alert messages.** Independent of Trenchfloor and Tickworks. Six named **deterministic Python stages**, not six autonomous AI models.

- Repository: https://github.com/joeypbrrr/wallet-hunters
- Site: https://joeypbrrr.github.io/wallet-hunters/
- Snapshot: `data/wallets.json` · source observations: `data/observations.json`
- **Hourly scheduler OFF. All seven optional features OFF.** The 3D scene animates; chain data is a timestamped static snapshot.

## Six agents

1. **Scout** — DexScreener market discovery plus GeckoTerminal trending Solana pool selection.
2. **Entry Cartographer** — recent observed swaps and earliest *observed* buyers; samples transaction signers via public Solana RPC.
3. **PnL Accountant** — conservative observed-lot FIFO matching, sell-sample win rates, partial monthly P&L, unknown starting inventory excluded.
4. **Integrity Analyst** — auditable high-frequency / anomalous / ultra-short-hold heuristics; optional wallet grouping, not cluster exclusion.
5. **Copyability Ranker** — baseline evidence ranking; optional delayed-entry capture and 3× move research score.
6. **Observatory Publisher** — mobile Three.js celestial vault, ranked observation queue, GMGN/Solscan links and ET agent logs.

## Actual data and limits

All API requests use HTTPS port 443 and no API keys. Tested on this box:

- `https://api.dexscreener.com/latest/dex/search?q=SOL`: **200**, Solana market scouting. Search is a sample, not every token or wallet. It does not expose wallet P&L.
- GeckoTerminal `/api/v2/networks/solana/trending_pools` and `/pools/{address}/trades`: **200**, token selection, current liquidity and recent trade windows (up to ~300 records per selected pool in this test). Calls are spaced 2.1 seconds apart, no 429 bypass. This is not launch history or full-wallet history. Paid APIs are not used.
- `https://api.mainnet-beta.solana.com`: **200** for `getSlot`, five `getTransaction` samples, and three `getSignaturesForAddress` probes. Signature probes each returned 1,000 records but reached back only minutes for these highly active wallets. Metadata alone does not reconstruct swaps or cost basis. Public RPC is rate-limited; unrestricted historical scanning is not implemented or claimed.
- Solscan legacy public account endpoint: TLS EOF failure. **Not used for data**. Solscan account links work independently.
- GMGN: **links only**, not scraped or used for data. No Cloudflare bypass.

**First real cycle:** 16 DexScreener Solana pairs; 10 GeckoTerminal token/pool windows; 2,995 swap observations; 946 distinct provider-reported wallets; 581 FIFO matched sell samples; five RPC transaction samples checked; no bot/wash heuristic exclusions. Eighteen wallets meet the *observed average-hold window alone*. Zero meet the 20-sell / three-observed-positive-month evidence floor. All rankings are provisional. The entire observed pool sample spans roughly 23h53m, but individual pool/wallet coverage is much shorter and uneven. **Days/weeks of complete wallet history and monthly consistency have not been established.** Do not present these as proven insider or copy-trade wallets.

Observed P&L is **not total-account P&L**: only matched quantities within sampled swaps, before network fees, protocol fees, token taxes, transfers, MEV, and unknown pre-existing inventory. Partial unmatched sells are excluded for the unknown quantity. A sell sample can be a partial exit, not an independent round-trip investment. Provider wallet attribution can be a router/program; only five transactions were independently sampled. Win rates are biased by sampling, survivorship and missing inventory.

Monthly bins use America/New_York; all are explicitly partial. Missing months are unknown, never zero. “Qualified sample only” requires 20 matched sells, at least three observed months, all net positive; it **still does not establish complete histories**. It is not an endorsement. Monthly consistency does not affect basic scores while its flag is OFF; it does affect the optional copy score because it is essential to that research objective.

## Scores and thresholds

Basic score = `(65% observed win rate + 35% bounded signed-log observed profit component) × sample confidence`. Confidence = `min(1, matched sells/20) × min(1, observed months/3)`. Unknown metrics remain null, not fabricated zero returns. Qualified samples sort first, then descending score; rows with no matched sells remain an unscored observation queue.

The **optional** copy score weights are shown per wallet: 25% win rate, 20% 3× move hit rate, 20% ≥35% capture rate, 10% ≥50% capture rate, 15% observed monthly consistency, 5% follower hold length, 5% current liquidity; multiplied by sample confidence. Missing copy price paths result in an unknown score, not a recommended wallet.

`config.json` holds:

- `min_avg_hold_seconds: 3600` and `max_avg_hold_seconds: 604800`: **latest owner rule replaces earlier 10-second/day rules**. Copy mode excludes an unknown average or average outside one hour–one week. Basic mode keeps those rows and labels them. Hold averages derive from matched observed FIFO sells.
- `big_move_multiple: 3`: **3× from entry = +200%**, not +300%. Counts only observed matched holding windows within the configured hold range, not price rises after the wallet exited. Weighted FIFO inferred entry time and first sampled entry price are approximations, not the true execution. Historical entry market cap and true peak are unknown.
- `copy_delay_seconds: 60`, `copy_entry_max_gap_seconds: 300`: first observed follower price at least 60 seconds after inferred entry, no more than 300 additional seconds later. Missing price → unknown.
- `copy_slippage_pct: 2` **each way**, plus conservative `copy_order_usd: 100 / current liquidity` impact each way (capped at 50%). `minimum_liquidity_usd: 25000` scales liquidity score. Current liquidity is a proxy, not historical executable depth.
- `copy_capture_targets_pct: [35,50]`: rate of matched one-hour–one-week windows whose **best later sampled price**, before the observed wallet sell, could have crossed those net thresholds. This is an **optimistic retrospective opportunity metric**, not an executable strategy or expected return. No intrabar fills, complete fade path, gas, token tax or live execution guarantee.
- `minimum_closed_samples: 20`, `minimum_observed_months: 3`.

**Limitation:** this free first snapshot is not sufficient for a reliable days/weeks historical copy backtest. Do not claim these thresholds identify consistently profitable wallets yet. A historical, indexed swap/price dataset or prolonged accumulation is needed. No accounts or paid data subscriptions were created.

## Optional features: all default OFF

Edit the relevant boolean under `features` in `config.json` from `false` to `true`, then run one approved research snapshot and publish it. No site toggle silently changes backend configuration.

| Flag | When enabled |
|---|---|
| `wallet_pnl_tracker` | Per-wallet monthly observed P&L table; ledger observations persist across runs. |
| `consistency_score` | Show profitable/loss month counts; blend consistency into basic score (80/20). Copy mode always includes consistency. |
| `wallet_tiers` | `unverified` by default; `sharp`: sample floor + ≥65% win rate + ≥60s median hold + ≥$25k liquidity; `whale (observed profit)`: sample floor + ≥$10k observed profit; `early-entry`: sample floor + ≥50% 3× hit rate + ≥60s median hold. Never “proven insider.” |
| `wallet_history_chart` | Per-wallet SVG monthly observed P&L chart. No synthetic past history. |
| `new_buy_alert_feed` | Site-only newly observed buys for the top ten current rows; event-ID deduplication. First-ever baseline does not flood alerts. Hourly, sampled, not real-time or complete wallet monitoring. |
| `copy_trade_ranking` | Apply the 1h–1week average-hold exclusion, delayed-entry 35/50% capture and 3× move score breakdown. |
| `cluster_detection` | Shared observed funder (2–10 recipients), direct RPC-observed SOL-transfer links, or co-buys within 3s across ≥3 distinct sampled tokens. Group linked wallets; don't drop clusters. |

Clusters have stable hash IDs, per-member GMGN and Solscan links, matched-sample weighted win rate/score and summed observed P&L, with evidence on the site and glowing gold constellation nodes. Shared funders can be exchanges; timing can be coincidence. Links **are not proof of shared control**. RPC transfer sampling is very small, so detection is incomplete. Summed member P&L may double-count internal economic exposure. Pure bot/wash suspicions are separately excluded by conservative, auditable heuristics, which also can misclassify; no definitive on-chain identity claims are made.

## Run manually / schedule (OFF)

```bash
cd /workspace/wallet-hunters
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
./scripts/run-once.sh             # public reads, local snapshot only
./scripts/run-once.sh --push      # ONLY after explicit approval to publish
# Only after Joey approves hourly publishing:
./scripts/start.sh --approved
# Stop only this project's runner:
./scripts/stop.sh
```

The local loop runs immediately when explicitly started, then once per 3,600 seconds, with a cycle lock. It commits timestamped JSON/agent-chat changes and pushes `main` once each successful cycle; GitHub Pages publishes from `/` on main. It is not installed as cron/systemd/GitHub Actions. `.run/hourly.pid` and `.run/hourly.log` are ignored. The box must remain online; this is not independent 24/7 hosting. `start.sh` refuses without `--approved`. No scheduler was started during this task.

The mobile site uses Three.js 0.160.0 from jsDelivr and Google Fonts; if CDN/WebGL fails, the data table remains accessible. Six agents occupy a circular celestial vault with astrolabe rings and evidence nodes — no office/kitchen/treadmills. Desktop/mobile screenshots are stored outside the repo in `/workspace/wallet-shots/`.

## Future ideas (not built)

1. Confidence intervals and out-of-sample validation to reduce small-sample leaderboard bias.
2. A historical liquidity/capacity stress test for multiple follower order sizes.
3. Wallet provenance evidence panels with exchange-funder exclusions and user-reviewed cluster links.

## $500 dormant copy-account allocation (latest update)

`copy_sim_starting_balance_usd: 500` is configured **per wallet and per research agent**, and `daily_profit_goal_usd: 300` is the comparison goal. Snapshot metadata initializes each dormant account at $500, zero trades. These are simulations only, not funded wallets; the six agents are research stages, not six independently validated trading strategies. The simulator is not running and no simulated orders were executed.

**Expected profit per day from $500: NOT ESTABLISHED. Capital needed for $300/day: UNKNOWN.** Neither a near-one-day uneven pool sample nor retrospectively capturable best prices justify an expected daily return. The site keeps both figures visible as unknown rather than inventing a projection. If a reliable net daily return `r` were established through a full historical and out-of-sample execution backtest, the arithmetic would be `$500 × r` per day and `$300 / r` capital; this is not a guarantee, and no such `r` has been established here. All optional feature flags and the hourly schedule remain OFF.
