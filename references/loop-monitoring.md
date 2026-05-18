# Loop Monitoring

## Scope

Use `scripts/position_monitor.py` for wallet-specific PT/YT lending-loop monitoring. It is separate from `yield_monitor.py`, which scans public opportunities.

The monitor supports:

- wallet-first discovery with `discover-wallet --address <wallet>`
- wizard-generated JSON config
- recursive loop simulation
- Morpho market/user reads through Morpho GraphQL
- live Morpho `marketPosition` reads by wallet + market unique key
- Aave V3 `getUserAccountData(address)` reads when RPC and Pool address are configured
- Pendle PT/YT/LP ERC-20 balance discovery when RPC is available
- health-factor/LTV/net-APY alerting
- SQLite history
- Telegram and Discord webhook delivery
- draft-only action plans for repay, add collateral, deleverage, or close

## Loop Math

For a target LTV `l` and `n` loop iterations:

```text
gross_collateral = equity * (1 + l + l^2 + ... + l^n)
debt = equity * (l + l^2 + ... + l^n)
ltv = debt / gross_collateral
```

Net APY estimate:

```text
annual_gross = gross_collateral * PT_or_YT_APY
annual_borrow = debt * borrow_APY
one_time_cost = max(gross_collateral, debt) * slippage_bps / 10000 + gas_usd
net_apy_before_cost = (annual_gross - annual_borrow) / equity
net_apy_after_cost = (annual_gross - annual_borrow - one_time_cost) / equity
```

Health factor approximation:

```text
health_factor = collateral_value * liquidation_threshold / debt_value
```

For Aave V3, prefer the real onchain `getUserAccountData` health factor when RPC is configured. For Morpho, use market/user API values plus configured collateral/debt where exact oracle-account data is unavailable.

Live value priority:

1. Morpho: use `marketPosition(userAddress, marketUniqueKey, chainId)` for collateral USD, borrow USD, margin USD, health factor, and liquidation price variation. Use `marketById` for borrow APY.
2. Aave V3: use `getUserAccountData(address)` for total collateral, total debt, LTV, liquidation threshold, and health factor. Configure `aave_base_decimals` per chain, defaulting to 8.
3. Manual fallback: use configured collateral/debt/APY values when no live adapter is available.

## Wallet Discovery

Use:

```bash
python3 scripts/position_monitor.py discover-wallet --address 0x... --write-config ~/.config/defimax/config.json
```

Discovery checks:

- Morpho `userByAddress` across configured chains and converts real positions into monitor loops.
- Aave V3 aggregate account data for configured chains with RPC/Pool data.
- Pendle active PT/YT/LP balances by checking ERC-20 `balanceOf` for active markets. This requires a configured RPC or a supported public RPC.

Discovery should never fabricate a loop. If no live position exists or the chain lacks an RPC/API adapter, return no position for that source and show errors or skipped sources in JSON.

## RPC Fallbacks

The skill ships with public RPC fallback lists for common EVM DeFi networks:

- Ethereum, Optimism, BNB Chain, Gnosis, Polygon, Sonic, HyperEVM, Mantle
- Base, Arbitrum, Avalanche, Linea, Blast, Scroll, Ink, Berachain, Katana

Resolution order:

1. configured env var, e.g. `ETH_RPC_URL`
2. configured literal `rpc_url`
3. bundled public RPC fallbacks

Run:

```bash
python3 scripts/position_monitor.py check-rpcs --chains ethereum,base,arbitrum,solana
```

Public RPCs are fallback-only. Prefer private RPCs for cron reliability, large wallet discovery, or frequent Pendle balance scans.

Bundled EVM RPC fallbacks cover the main Aave/Pendle/Morpho network set, including Ethereum, Optimism, BNB Chain, Gnosis, Polygon, Base, Arbitrum, Avalanche, Linea, Scroll, Sonic, Mantle, Metis, ZKsync Era, Celo, Soneium, Plasma, Fantom, Harmony, HyperEVM, Berachain, Katana, Ink, Monad, Unichain, World Chain, Mode, Fraxtal, Lisk, Sei, Etherlink, Kaia, Plume, Bitlayer, Corn, and other Morpho deployment networks where a stable public RPC is known.

Aave V3 account discovery requires both an EVM RPC and the correct Aave `POOL` address. The default config includes Pool addresses from the Aave address book for the main supported Aave V3 networks. If a new Aave market launches or a specialized same-chain market is needed, add its `aave_pool` explicitly in config.

Solana is a separate RPC family. The config includes Solana mainnet RPC fallback, `check-rpcs` support, and Solana wallet address acceptance in `discover-wallet`, but live Solana DeFi position discovery requires a protocol-specific parser/indexer adapter and must not be treated as ERC-20/Pendle/Aave/Morpho data.

Solana adapter targets include:

- Meteora DLMM: use program ID `LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo`, pool list `https://dlmm-api.meteora.ag/pair/all`, and the Meteora DLMM SDK `getAllLbPairPositionsByUser(connection, userPubKey)` for wallet positions.
- Meteora DAMM v2: add as a separate adapter because its account model differs from DLMM.
- Kamino, Drift, MarginFi, and Jupiter: add protocol-specific parsers or indexer-backed readers before claiming live wallet monitoring.

Cron delivery should use `alerts.min_interval_hours` to avoid duplicate alert spam. A warning/critical alert can be sent again after that interval if the condition persists.

## Execution Guardrail

The skill must never ask for, store, or use seed phrases/private keys. It may generate a transaction plan, but signing must happen through walletconnect-mqc or another wallet-side confirmation path.

Unattended signing and automatic liquidation protection are intentionally disabled. The safe automation boundary is:

1. monitor
2. alert
3. generate draft action plan
4. require explicit user confirmation
5. require wallet approval of exact transaction

## Unsupported As Guarantees

Do not claim:

- legal, tax, or investment advice
- guaranteed APY safety
- guaranteed liquidation prevention
- complete exploit/news coverage
- autonomous protection without wallet and protocol-specific transaction adapters
