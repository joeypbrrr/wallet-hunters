# Wallet Hunters — The Astral District

Read-only, public on-chain wallet research with **50 executable hunting jobs**, a Three.js city, and a fully 3D observatory. Separate from Trenchfloor and Tickworks. **No private keys, funded wallets, transactions, real trading, or external alert messages.**

- Repo: https://github.com/joeypbrrr/wallet-hunters
- Pages: https://joeypbrrr.github.io/wallet-hunters/
- Source snapshots: `data/wallets.json`, `data/observations.json`
- All feature flags ON by owner approval. One local hourly publisher is ON. No Ethereum-mainnet ingestion.

## Fifty real hunters

`agents.json` contains 50 named profiles, each with an ID, chain, job, personality, quirk, specialization, neighborhood and **distinct executable slice configuration**. These are deterministic research workers, **not 50 LLM services**. The fictional personality does not manufacture evidence or place orders.

- **30 Solana hunters** — five liquidity bands × six holding windows: 1–2h, 2–6h, 6–12h, 12–24h, 1–3d and 3–7d.
- **15 BNB hunters** — five liquidity bands × three windows: 1–6h, 6–24h and 1–7d.
- **5 Robinhood hunters** — five liquidity bands, 1h–7d holding window.

Liquidity bands: $25k–$100k, $100k–$500k, $500k–$2m, $2m–$10m, and $10m+. Allocations are a provisional 60/30/10 research weighting, not a measured market-share claim. Every cycle executes all 50 filters/scorers over real shared evidence; each contributes its candidate set into the master queue. An empty slice is logged as `completed_no_match`, not hidden or filled with fake wallets. `data/hunting-results.json` exposes the individual runs, best candidate, sample count and per-agent paper account.

`research.FetchQueue` is the **only fetch queue** used by the pipeline. Requests are serial, identical requests are cached in-cycle, and provider-host spacing is currently **13 seconds for GeckoTerminal, 5.1 seconds for Solana RPC and 1.1 seconds for EVM RPC**, with a conservative two selected pools per chain. HTTP 429 suspends that host for the rest of the cycle; no bypass or same-cycle retry. Earlier tests reached GeckoTerminal rate limits, so source errors and cached/unavailable chain status are explicitly published. One chain failing never invents data for another.

## City + fully 3D interior

City districts: Solana / Signal Quarter, BNB / Jade Ledger, Robinhood Heights. The central landmark contains the preserved dark observatory. City/Observatory buttons smoothly move the perspective camera; `#city` opens the exterior directly.

All room furniture, 50 stations, desks, chairs, working figures, clock-in board and shared-lessons board are **Three.js meshes**. Boards and station screens carry canvas textures for real snapshot text. No flat room image or CSS mock substitutes for the space. Every station and commuting figure maps to one of the 50 real profile IDs. Tap a station/agent to inspect its actual slice, current best wallet, links and paper-account state. Commutes/clock-ins are cosmetic representations; real job execution is evidenced separately by timestamps and per-agent results. The phone renderer caps pixel ratio at 1 and aims at 30 rendered frames per second; actual performance depends on the phone/GPU. An accessible HTML table remains usable without WebGL/CDN access.

## Three supported chains, verified

| Chain | Provider IDs | RPC | Explorer / links |
|---|---|---|---|
| Solana | DexScreener `solana`, GeckoTerminal `solana` | `https://api.mainnet-beta.solana.com` | Solscan + GMGN `/sol/address/` |
| BNB mainnet, chain ID **56** | `bsc` / `bsc` | `https://bsc-rpc.publicnode.com` | BscScan + GMGN `/bsc/address/` |
| Robinhood mainnet, chain ID **4663** (`0x1237`) | `robinhood` / `robinhood` | `https://rpc.mainnet.chain.robinhood.com` | Official `https://robinhoodchain.blockscout.com`; GMGN support unverified, so **no GMGN link** |

Robinhood is **live mainnet**, not the testnet (46630). Verified from the [official connecting guide](https://docs.robinhood.com/chain/connecting/), live `eth_chainId`, DexScreener results, GeckoTerminal network listing and live pool/trade feeds. Its native gas token being ETH does **not** mean this pipeline queries Ethereum mainnet. The official explorer API stats response was not JSON in this test, so that API is not a data dependency. No accounts or API keys were created.

All reads use HTTPS port 443. DexScreener discovers pairs/current liquidity. GeckoTerminal supplies timestamped recent swap windows, usually up to about 300 trades/pool. These are **not full-chain, launch or full-wallet histories**. Public Solana RPC checks a small transaction/signer sample and SOL-transfer evidence.

### Proper EVM parsing

`research.verify_evm` queries `eth_chainId`, `eth_blockNumber`, bounded `eth_getLogs` on a selected pair/pool, `token0()`, `token1()`, and token decimals through `eth_call`. It decodes standard V2 Swap unsigned amount words and V3 signed amount deltas using Ethereum Keccak topics. It reads transaction origin, successful receipts, native gas fees and block timestamps; it does **not** misidentify the event's router/recipient as the owner.

Only a bounded recent block window and three log transactions are independently checked per EVM chain. A quiet pool can have zero logs in that window. Unsupported pool ABIs fail explicitly. Raw logs with no historical USD price remain unpriced and are excluded from P&L/copy fills. Current DexScreener spot prices are **not** silently used as historical execution prices. Smart-account/bundler attribution and missing history remain limitations.

## Ranking, filters and limits

- Copy mode requires observed average hold **1 hour–1 week** (`min_avg_hold_seconds=3600`, `max_avg_hold_seconds=604800`) and current sampled mean liquidity ≥$25k. Unknown hold or liquidity does not pass.
- Bot/wash exclusions: >60 sampled swaps/minute, repeated sub-2-second matched holds, or majority provider-anomalous trades. These are incomplete heuristics, **not proof** of MEV or manipulation.
- Qualification floor: ≥20 matched source sells and ≥3 observed positive monthly bins. All bins remain partial; reaching this floor still does not certify complete history. Current tests have **zero fully qualified wallets**.
- Source P&L is FIFO-matched observed lots, **before fees**, excluding unknown starting inventory. A partial sell is a sample, not an independent complete investment. Missing months are unknown, never zero. Monthly boundaries use America/New_York.
- Copy score weights: 25% observed win rate, 20% 3× move hit rate, 20% ≥35% best-price capture, 10% ≥50% capture, 15% observed monthly consistency, 5% hold length, 5% liquidity; multiplied by sample confidence. Minimum-history confidence strongly discounts thin samples.
- **3× means +200%**, not +300%. Only observed matched holding windows are checked, with weighted-FIFO entry-time approximation. Historical entry market cap, true peak and complete fade path are unknown.
- Best-price capture is a diagnostic, **not executable P&L**: first sampled entry ≥60s after the inferred buy, maximum 300s additional entry gap, modeled each-side slippage/fees, and best sampled later price before the source exit. Actual paper replay below does not use future peaks to choose its exit.
- Consistency is essential to copy ranking. Its separate flag also controls the optional basic-score blend.

## Completed $500 copy simulation

Two clearly separated account types:

1. **Per-wallet retrospective diagnostics** replay the available sampled market tape from a fresh $500. Wallet selection is retrospective and therefore biased; this is research, not a live-performance claim.
2. **Fifty independent forward-observation hunter accounts** start at $500. When a hunter first finds a real slice candidate, its selection time and followed wallet are persisted in `data/agent-account-state.json`. Only source buys observed **after that selection time** can enter its account. Selection is not silently reset to the latest winner each hour. An agent with no candidate stays at $500 with zero fills. Replays deterministically reconstruct state from retained observations, preventing restart double-counting. Current best research candidate can differ from the locked paper-follow target; both are shown.

Chronological replay rules:

- $100 maximum per entry, ≤5 open positions, finite cash, minimum order $10, no leverage.
- First observed price ≥60s after a source buy; skip if no price within 300 extra seconds.
- 2% slippage each side plus $100/current-liquidity impact. This is a conservative model, **not measured historical depth**.
- Modeled each-side fees: Solana 125 bps + $0.01 network; BNB 30 bps + $0.05; Robinhood 30 bps + $0.005. These are **configurable assumptions**, not claims about actual pool fees/gas/token taxes.
- Exit at the first observed tick reaching **net +35%**, otherwise the first observed source sell (entire copied token position) or one-week timeout if a price tick is available. No invented price when a tape gap exists. No stop-loss is assumed.
- The ≥50% best-price capture rate is shown separately; it is **not a second secretly executed strategy**.
- Closed fills include entry/exit timestamps, modeled fees, P&L, exit reason and chain-explorer evidence. Open positions are marked from the last observed price, explicitly not realized profit.
- On reaching +$300 realized profit in an **ET day**, that account stops new entries for that day; existing positions can still exit. The ET-day latch is reconstructed from deduplicated retained fills and survives restarts.

### $300/day feasibility

Expected net profit/day from $500: **insufficient data**. Capital needed for $300/day: **insufficient data**. No complete days/weeks/months execution dataset or out-of-sample validation exists. Neither observed source profits nor best-price opportunities justify a forecast.

Arithmetic only: $300/$500 = **60% net per day**. A $100 position earning the simulator's +35% net target earns $35; **at least nine such winning fills** would be needed for $300 with no losing fills. A hypothetical +50% on $100 earns $50, requiring six, but +50% is not this simulator's executed target. An all-in $500 +35%/+50% move would earn $175/$250, still below $300. These are not predictions. Fifty separate $500 hunter accounts are **$25,000 hypothetical notional**, not one shared $500 wallet and not real funding.

If a defensible expected net daily return `r` were ever established, arithmetic would be `$500 × r` and `$300 / r`; none has been established here, and there is no guaranteed capital amount that yields $300/day.

## Learning, lessons, badges and charts

- Every genuine **simulated closed loss** can generate an evidence-linked loss review, identifying the modeled delayed/slipped entry, fee drag and exit condition. It never claims to know the original source trader's intentions.
- The shared lessons checklist is deduplicated, evidence-backed and **suggestion only**. It never changes flags, thresholds or strategy automatically.
- Per-wallet source monthly P&L, copy monthly P&L and observed-price marked-equity charts show actual observations/replay points only. Missing data is labeled; no fabricated past curves.
- `unverified` tier is default. `sharp`: evidence floor, ≥65% win rate, ≥60s median hold and ≥$25k mean liquidity; `whale (observed profit)`: evidence floor + ≥$10k observed source profit; `early-entry`: evidence floor + ≥50% 3× hit rate and ≥60s median hold. These labels do not prove insider status.
- `Standout` requires the evidence floor **and ≥$300 net simulated closed profit today**, not unrealized or source-wallet profit. No badge is awarded merely for a thin 100% win-rate sample.
- New-buy alerts are deduplicated, sampled, **site only**, with no messaging connector. Hourly observation is not a real-time complete-wallet feed.

## Clusters

Within each chain, group—not discard—wallets sharing RPC-observed funding (bounded recipients), direct SOL transfers, or co-buy timing within 3s across ≥3 distinct observed tokens. Cluster IDs, members, links and combined sampled stats are published. Funding/timing evidence is very incomplete; exchange funders and coincidence can falsely link wallets. Combined source P&L can double-count shared economic exposure. **No cross-chain group is asserted without proof**; this version asserts none.

## Flags and operation

All booleans under `features` in `config.json` are currently ON:

`wallet_pnl_tracker`, `consistency_score`, `wallet_tiers`, `wallet_history_chart`, `new_buy_alert_feed`, `copy_trade_ranking`, `cluster_detection`, `copy_account_simulation`, `agent_learning`, `lessons_board`, `daily_goal_tracker`, `standout_badges`.

Set any to `false` to disable that feature, then run/publish a research cycle. No UI control silently changes backend configuration. All features are implemented; **insufficient historical data is not disguised as a finished profitable strategy**.

```bash
cd /workspace/wallet-hunters
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
./scripts/run-once.sh           # public reads; local snapshot
./scripts/run-once.sh --push    # approved timestamped GitHub publish
./scripts/start.sh --approved --delay-first  # only if no runner is already active
./scripts/stop.sh
```

The existing runner reads the scripts and Python modules anew every cycle, so deployed code changes are picked up without starting a duplicate. It has a project-local scheduler flock and per-cycle flock. `.run/hourly.pid`, `.run/next-cycle-epoch` and `.run/hourly.log` record its state. It commits timestamped data and pushes once per successful hourly cycle; Pages serves main `/`. No cron, systemd or extra GitHub Actions schedule was installed. The box must stay online; GitHub Pages alone does not run scans. No Trenchfloor or Tickworks files/processes/configuration are accessed or changed.

## Future ideas, not built

1. Verified archive/indexer history and out-of-sample validation with confidence intervals.
2. Historical order-book/depth and tax simulation for different follower sizes.
3. Human-reviewed provenance panels and exchange-funder exclusions for cluster evidence.
