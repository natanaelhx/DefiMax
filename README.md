# Defimax

Defimax is an OpenClaw/Codex skill for DeFi yield discovery, Pendle PT/YT/LP monitoring, lending-loop risk checks, and Telegram-ready alerts.

## Skill Path

The Skill Builder package lives in:

```text
defimax/
```

This keeps the runtime skill folder clean. `README.md` stays at the repository root because the Skill Builder package itself should contain only `SKILL.md`, optional `agents/`, `references/`, `scripts/`, and assets.

## What It Does

- Scans DeFi yield opportunities using DefiLlama Yields and Pendle Core.
- Splits Pendle markets into `PT`, `YT`, and `LP` rows.
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
cd defimax
python3 scripts/yield_monitor.py --stable-only --risk-profile balanced --min-tvl-usd 5000000 --limit 10
```

Preview Telegram delivery:

```bash
cd defimax
python3 scripts/telegram_delivery.py --dry-run --stable-only --risk-profile balanced --min-tvl-usd 5000000 --limit 6
```

Monitor wallet loops:

```bash
cd defimax
python3 scripts/position_monitor.py wizard --config ~/.config/defimax/config.json
python3 scripts/position_monitor.py monitor --config ~/.config/defimax/config.json
```

## Safety

Defimax does not ask for seed phrases, private keys, mnemonics, or keystores. It can monitor, alert, and draft action plans, but signing must happen through explicit wallet-side approval.

Outputs are research and operational risk monitoring, not financial, legal, or tax advice.
