# Defimax

Defimax is an OpenClaw/Codex skill for DeFi yield discovery, Pendle and Solana PT/YT/LP monitoring, lending-loop risk checks, and Telegram-ready alerts.

## Skill Path

The Skill Builder package lives at the repository root:

```text
SKILL.md
agents/
references/
scripts/
```

That is the direct Skill Builder layout. `README.md` is only for GitHub repository context; the runtime skill entrypoint is `SKILL.md`.

## What It Does

- Scans DeFi yield opportunities using DefiLlama Yields and Pendle Core.
- Splits Pendle markets into `PT`, `YT`, and `LP` rows.
- Loads Solana `PT`/`YT` markets from indexed JSON sources for Exponent/RateX-style markets.
- Monitors configured wallet loops with LTV, health factor, net APY, slippage/gas impact, and maturity risk.
- Reads Aave V3 account data when RPC and Pool address are configured.
- Reads Morpho market/user data through Morpho GraphQL.
- Checks Pendle PT/YT/LP wallet balances on supported EVM chains.
- Includes Solana RPC support and adapter targets for Meteora, Kamino, Drift, MarginFi, and Jupiter.
- Generates Telegram emoji reports and guarded action plans.

## Install / Use

Use the skill slug:

```text
$defimax
```

Run from the skill directory:

```bash
python3 scripts/yield_monitor.py --stable-only --risk-profile balanced --min-tvl-usd 5000000 --limit 10
```

Scan Solana PT/YT markets from an indexer or exported snapshot:

```bash
python3 scripts/yield_monitor.py --no-defillama --no-pendle --solana-yield-input-json solana-yield-markets.json --position-types pt,yt --chains solana
```

Preview Telegram delivery:

```bash
python3 scripts/telegram_delivery.py --dry-run --stable-only --risk-profile balanced --min-tvl-usd 5000000 --limit 6
```

Monitor wallet loops:

```bash
python3 scripts/position_monitor.py wizard --config ~/.config/defimax/config.json
python3 scripts/position_monitor.py monitor --config ~/.config/defimax/config.json
```

## Safety

Defimax does not ask for seed phrases, private keys, mnemonics, or keystores. It can monitor, alert, and draft action plans, but signing must happen through explicit wallet-side approval.

Outputs are research and operational risk monitoring, not financial, legal, or tax advice.
