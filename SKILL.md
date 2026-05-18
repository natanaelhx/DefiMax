---
name: defimax
description: Find, rank, monitor, and prepare alerts for DeFi crypto yield opportunities and configured wallet loops across Pendle PT/YT/LP, Solana PT/YT markets such as Exponent/RateX indexed sources, DefiLlama Yields, Aave, Morpho, Euler-style lending markets, stablecoin pools, liquid staking, restaking, LP pools, and vault protocols. Use when the user asks Defimax/OpenClaw to scan APY, fixed yield, passive income, farming, DeFi yields, Pendle markets, Solana yield tokens, PT/YT lending loops, health factor, liquidation risk, recurring monitoring every 6 hours or daily, risk-filtered opportunities, Telegram/Discord alerts, cron setup, or guarded transaction/action plans.
---

# Defimax

## Overview

Use this skill to discover DeFi yield opportunities, monitor configured PT/YT lending loops, rank risk-adjusted opportunities, and prepare recurring alerts for the user. Treat every output as research and operational risk monitoring, not financial, legal, or tax advice.

## Operating Workflow

1. Capture constraints before ranking if they are not obvious:
   - target assets or symbols, especially stablecoins versus volatile assets
   - chains allowed or excluded
   - minimum TVL/liquidity
   - risk profile: `conservative`, `balanced`, or `aggressive`
   - schedule: `6h`, `daily`, or manual
   - alert destination if a notification tool exists
   - protocols to include or exclude

2. Gather yield data:
   - Prefer the installed Pendle skill/tooling for Pendle-specific fixed yield, PT/YT/LP, expiry, points, and external protocol checks.
   - Run `scripts/yield_monitor.py` for a merged DefiLlama + native Pendle Core + Solana PT/YT indexed-source scan.
   - For Solana PT/YT markets such as Exponent or RateX, pass a trusted indexed JSON file with `--solana-yield-input-json` or a URL through `DEFIMAX_SOLANA_YIELD_MARKETS_URL` / `--solana-yield-url`.
   - Run `scripts/position_monitor.py` for wallet-specific PT/YT lending loops, health factor, liquidation-risk, history, and alert delivery.
   - Read `references/data-sources.md` before changing endpoints, parsers, or Pendle integration details.
   - Read `references/loop-monitoring.md` before changing loop math, execution guardrails, or wallet-specific monitoring.

3. Normalize each opportunity into the same fields:
   - protocol/project, chain, pool id, symbol, pool metadata
   - APY, base APY, reward APY, and reward share
   - TVL/liquidity in USD
   - stablecoin flag, impermanent-loss risk, exposure type, outlier flag
   - position type: `PT`, `YT`, `LP`, or generic `pool`
   - Pendle maturity, implied APY, YT floating APY, aggregated LP APY, points, and external integrations when available
   - Solana PT/YT protocol, market/source URL, maturity, fixed/floating APY, TVL, and liquidity when supplied by the indexer

4. Filter before presenting:
   - default to minimum TVL of at least `$1,000,000` unless the user asks for early-stage opportunities
   - exclude DefiLlama outliers unless the user explicitly wants aggressive scanning
   - flag reward-heavy APYs where most yield comes from incentives
   - flag LP or multi-asset exposure when impermanent loss can matter
   - separate `PT`, `YT`, and `LP` opportunities from generic variable DeFi pool yields

5. Rank with risk-adjusted scoring:
   - reward sustainable base yield, high TVL, stablecoin exposure, and known protocols
   - penalize outliers, low TVL, high reward dependency, IL risk, very high APY spikes, and short data history
   - never rank by headline APY alone

6. Produce a notification-ready report:
   - lead with the best 3-10 opportunities
   - include APY breakdown, TVL, chain, protocol, symbol, why it triggered, and risk flags
   - include "check before action" notes: contract/app URL, withdrawal lockups, reward token liquidity, bridge risk, oracle/depeg risk, and maturity date for Pendle
   - say when there are no opportunities that pass filters

7. For configured user loops:
   - prefer `position_monitor.py discover-wallet --address <wallet>` so the user can start from a wallet address instead of manually entering every position
   - use `position_monitor.py wizard` to create config
   - calculate loop exposure, debt, LTV, health factor, net APY, slippage/gas impact, and days to maturity
   - use live protocol values first when configured, falling back to manual config values only when live reads are unavailable
   - read Aave V3 collateral, debt, LTV, liquidation threshold, and health factor onchain when wallet, RPC, and Pool address are configured
   - read Morpho market borrow APY plus wallet position collateral, debt, margin, health factor, and liquidation-distance when market unique key and wallet are configured
   - store every snapshot in SQLite history
   - send Telegram/Discord alerts only when configured and requested, with alert interval control to reduce duplicate cron spam
   - generate draft action plans for repay/add-collateral/deleverage/close, but require explicit wallet confirmation for any transaction

## Script Usage

Run from the skill folder or pass the full path:

```bash
python3 scripts/yield_monitor.py --risk-profile balanced --min-tvl-usd 1000000 --limit 10
```

Conservative stablecoin scan:

```bash
python3 scripts/yield_monitor.py --stable-only --risk-profile conservative --min-tvl-usd 5000000 --limit 10
```

Pendle-only scan including PT, YT, and LP positions:

```bash
python3 scripts/yield_monitor.py --no-defillama --position-types pt,yt,lp --min-tvl-usd 1000000 --limit 15
```

Pendle YT-only scan:

```bash
python3 scripts/yield_monitor.py --no-defillama --position-types yt --limit 10
```

Solana PT/YT scan from an indexed JSON snapshot:

```bash
python3 scripts/yield_monitor.py --no-defillama --no-pendle --solana-yield-input-json solana-yield-markets.json --position-types pt,yt --chains solana --min-tvl-usd 1000000 --limit 15
```

Solana PT/YT scan from an indexer URL:

```bash
DEFIMAX_SOLANA_YIELD_MARKETS_URL=https://example.com/solana-yield-markets.json python3 scripts/yield_monitor.py --position-types pt,yt --chains solana
```

Create a wallet/loop monitoring config:

```bash
python3 scripts/position_monitor.py wizard --config ~/.config/defimax/config.json
```

Discover DeFi positions from a wallet address and generate a monitor config:

```bash
python3 scripts/position_monitor.py discover-wallet --address 0x... --write-config ~/.config/defimax/config.json
```

Discover only selected chains:

```bash
python3 scripts/position_monitor.py discover-wallet --address 0x... --chains ethereum,base --write-config ~/.config/defimax/config.json
```

Check integrated RPC fallbacks:

```bash
python3 scripts/position_monitor.py check-rpcs --chains ethereum,base,arbitrum,solana
```

Write a non-interactive example config:

```bash
python3 scripts/position_monitor.py wizard --write-example --config ~/.config/defimax/config.json
```

Monitor configured loops, store SQLite history, and print report:

```bash
python3 scripts/position_monitor.py monitor --config ~/.config/defimax/config.json
```

Send Telegram/Discord alerts for warnings/critical states:

```bash
python3 scripts/position_monitor.py monitor --config ~/.config/defimax/config.json --send-alerts --json
```

Preview the current opportunity report in Telegram emoji format:

```bash
python3 scripts/telegram_delivery.py --dry-run --stable-only --risk-profile balanced --min-tvl-usd 5000000 --limit 6
```

Send the current opportunity report to Telegram:

```bash
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 scripts/telegram_delivery.py --stable-only --risk-profile balanced --min-tvl-usd 5000000 --limit 6
```

Simulate a PT loop:

```bash
python3 scripts/position_monitor.py simulate-loop --capital-usd 10000 --target-ltv 0.65 --iterations 3 --liquidation-threshold 0.86 --pt-apy 0.18 --borrow-apy 0.07
```

Generate a guarded action plan:

```bash
python3 scripts/position_monitor.py tx-plan --config ~/.config/defimax/config.json --loop "PT apyUSD loop on Morpho" --action repay
```

Recurring monitor state for 6-hour or daily alerts:

```bash
python3 scripts/yield_monitor.py --state ~/.cache/defimax/state.json --alert-apy-change 1.0 --json
```

The first stateful run establishes a baseline. Add `--emit-initial-alerts` only when the user wants the first run to alert on every current top opportunity.

Use `--json` when another tool will post to Telegram, Discord, email, Slack, or a local notification channel. If no notification integration is available, prepare the alert text and tell the user how to wire the command into their chosen scheduler.

## Loop Monitoring

Use `position_monitor.py` for wallet-specific monitoring. It reads a JSON config that contains wallet address, chain RPC env vars, protocol adapters, loop definitions, risk thresholds, and alert destinations.

Wallet-first discovery:

1. Run `discover-wallet --address <wallet>`.
2. Use detected Morpho/Aave/Pendle positions to write a config.
3. Review the generated config before enabling cron.
4. Run `monitor --send-alerts` on cron.

Default value priority:

1. live Morpho `marketPosition` / `marketById` when `morpho_market_unique_key` is configured
2. live Aave V3 `getUserAccountData(address)` when RPC and Pool are configured
3. configured manual values as fallback

Supported monitoring surfaces:

- public Pendle PT/YT/LP APYs from Pendle Core
- Solana PT/YT market APYs from trusted indexed JSON sources for Exponent/RateX-style markets
- wallet PT/YT/LP balances through ERC-20 `balanceOf` when a public or configured RPC is available
- Morpho market and wallet position data through Morpho GraphQL when configured
- Aave V3 real account collateral, debt, LTV, liquidation threshold, and health factor through `getUserAccountData(address)` when RPC and Pool are configured
- manual/configured loop debt and collateral for protocols that do not expose a stable public API
- SQLite history at the configured `database` path
- Telegram and Discord delivery with tokens/webhooks stored in environment variables

Integrated RPC fallbacks are bundled for the main Aave/Pendle/Morpho EVM surface area: Ethereum, Optimism, Flare, Cronos, XDC, BNB Chain, Gnosis, Unichain, Monad, Polygon, Sonic, TAC, Fantom, Fraxtal, ZKsync Era, World Chain, HyperEVM, Metis, Lisk, Sei, Soneium, Abstract, Mantle, Kaia, Plasma, Base, Mode, Arbitrum, Celo, Etherlink, Avalanche, Zircuit, Linea, Blast, Plume, Bitlayer, Scroll, Ink, Berachain, Katana, Harmony, and Corn. Prefer private RPC env vars for reliability; public endpoints are fallback-only and can rate-limit.

Aave V3 Pool addresses are bundled where the Aave address book exposes a mainnet `POOL`: Ethereum, Optimism, BNB Chain, Gnosis, Polygon, Sonic, Fantom, ZKsync Era, Metis, Soneium, Mantle, Plasma, Base, Arbitrum, Celo, Avalanche, Linea, Scroll, and Harmony. Same-chain specialized Aave markets, such as Ethereum Lido/EtherFi, should be added as explicit extra loop configs to avoid duplicate wallet discovery.

Solana mainnet RPC is bundled for health checks and future adapters. `discover-wallet` accepts Solana wallet addresses and reports adapter status, but do not claim Solana DeFi position discovery is complete until a Solana-specific adapter is added for the target protocol, such as Exponent, RateX, Meteora DLMM/DAMM v2, Kamino, Drift, MarginFi, Jupiter, or another indexed source. Solana does not use EVM `eth_call`, ERC-20 `balanceOf`, Aave Pool, Pendle PT/YT, or Morpho Blue adapters. Solana PT/YT market ranking is supported through the Solana yield index input, not by treating Solana markets as Pendle markets.

Do not scrape protected Solana app pages and then invent missing APY, TVL, liquidity, expiry, or depth. If Exponent/RateX data is unavailable from a trusted API/export/indexer, report that the source is missing and keep the market out of ranked live opportunities.

For Euler-style markets, configure the loop using vault/pair data, collateral, debt, LTV, LLTV, borrow APY, and health thresholds. Treat Euler as config-driven until a protocol-specific adapter for the target vault is added.

Cron alerts use `alerts.min_interval_hours` from config to avoid sending the same warning every run. Critical states should still be reviewed immediately whenever they appear.

If discovery finds no positions, return an empty report clearly. Do not invent loops.

## Execution Guardrails

The skill may create action plans, not unattended transactions. It must never ask for seed phrase, private key, mnemonic, or keystore.

Allowed:

- monitor and alert
- calculate health factor, liquidation buffer, loop net APY, and maturity risk
- generate a draft action plan for repay, add collateral, deleverage, or close
- hand off to `walletconnect-mqc` only after explicit user confirmation and wallet-side approval

Not allowed:

- unattended signing
- storing private keys
- claiming that liquidation protection is guaranteed
- claiming that high APY is safe
- giving legal, tax, or investment advice as professional advice

If the user asks for fully autonomous execution, keep the automation boundary at alert + draft plan + explicit confirmation + wallet approval.

## Pendle Procedure

For Pendle-focused requests:

1. Query active markets using Pendle data tooling or `scripts/yield_monitor.py --no-defillama`.
2. Split every active market into separate `PT`, `YT`, and `LP` rows.
3. Rank `PT` fixed yield by implied APY.
4. Rank `YT` by YT floating APY and always flag it as higher risk because YT is yield-token exposure, not redeemable principal.
5. Rank `LP` by aggregated APY and show underlying, swap fee, PENDLE/reward APY, and maturity.
6. Apply liquidity/TVL thresholds and note maturity dates.
7. Parse points and external protocol integrations when present.
8. Prefer cross-chain Pendle core API endpoints for custom integrations; avoid Pendle BFF endpoints.

Use Pendle outputs as explicit position types because fixed maturity PT yield, YT exposure, and LP positions have different risk semantics than generic lending/vault APYs.

## Solana PT/YT Procedure

For Solana fixed-yield or yield-token requests:

1. Use `--solana-yield-input-json` or `DEFIMAX_SOLANA_YIELD_MARKETS_URL` to load Exponent/RateX-style indexed markets.
2. Normalize Income Token/fixed-yield markets as `PT` and Farm/yield-token markets as `YT`.
3. Require real APY, TVL/liquidity, chain, symbol, and maturity from the indexer before ranking.
4. Rank Solana `PT` by fixed/implied APY and flag maturity and indexed-source risk.
5. Rank Solana `YT` separately and always flag principal-not-redeemable/floating-yield risk.
6. Include the official source/app URL when supplied so the user can verify market depth and route before any action.

## Scheduling Guidance

Use a 6-hour schedule for active opportunity monitoring and a daily schedule for conservative reports. Suggested cron shapes:

```cron
0 */6 * * * python3 /home/openclaw/.openclaw/skills/defimax/scripts/yield_monitor.py --state ~/.cache/defimax/state.json --json
```

```cron
0 12 * * * python3 /home/openclaw/.openclaw/skills/defimax/scripts/yield_monitor.py --stable-only --risk-profile conservative --state ~/.cache/defimax/stable-state.json
```

Do not create or modify a user's scheduler unless explicitly asked. When asked to enable monitoring, verify the target channel and write a small wrapper only if needed by that channel.

For loop monitoring, print a cron line without installing it:

```bash
python3 /home/openclaw/.openclaw/skills/defimax/scripts/position_monitor.py install-cron --schedule 6h --config ~/.config/defimax/config.json
```

## Alert Rules

Alert only when one of these is true:

- a new opportunity enters the filtered top results
- APY changes by at least the configured threshold
- TVL crosses the configured minimum
- a risk flag changes materially, especially outlier, low TVL, or reward-heavy status
- a Pendle market is close to maturity or a new high-liquidity market appears

Suppress repeated alerts for unchanged pools. Include both the new value and the prior value when state is available.
