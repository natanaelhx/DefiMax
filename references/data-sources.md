# Data Sources

## DefiLlama Yields

Use DefiLlama Yields for cross-protocol first-pass discovery.

- Primary public endpoint: `https://yields.llama.fi/pools`
- Historical pool chart: `https://yields.llama.fi/chart/{pool}`
- Authentication: none for normal public usage
- Important fields: `pool`, `project`, `chain`, `symbol`, `tvlUsd`, `apy`, `apyBase`, `apyReward`, `stablecoin`, `ilRisk`, `exposure`, `outlier`, `poolMeta`, `underlyingTokens`, `rewardTokens`

APY values from DefiLlama Yields are percentages, not decimals. A value of `12.5` means `12.5%`.

Filtering guidance:

- Exclude `outlier` pools by default.
- Treat `apyReward` as lower quality than `apyBase` unless the user wants incentive farming.
- Treat `ilRisk` and multi-asset symbols as warnings, not automatic exclusions.
- Use TVL thresholds to avoid illiquid pools and stale incentive traps.

## Pendle

Use the installed Pendle skill when available because it exposes synced market data, points, and external protocol integrations directly.

For custom API work, use Pendle public Core API, not BFF:

- Core docs: `https://api-v2.pendle.finance/core/docs`
- Cross-chain markets: `GET /v2/markets/all`
- Chain-scoped history: `GET /v3/{chainId}/markets/{address}/historical-data`

Pendle values can be decimals in some tools and percentages in others. Confirm the shape before mixing with DefiLlama values. In the installed Pendle data skill, fields such as `details_impliedApy`, `details_underlyingApy`, and `details_aggregatedApy` are decimals, so `0.12` means `12%`.

Native Pendle Core `GET /v2/markets/all` also returns decimal APY values. Split active markets into:

- `PT`: `details.impliedApy * 100`, fixed maturity principal-token yield.
- `YT`: `details.ytFloatingApy * 100`, yield-token floating yield exposure. Flag as higher risk because YT is not redeemable principal.
- `LP`: `details.aggregatedApy * 100`, Pendle AMM LP yield. Show `details.underlyingApy`, `details.swapFeeApy`, and `details.pendleApy` separately when available.

Use `details.totalTvl` for TVL and `details.liquidity` as a separate liquidity sanity check. A high APY with low Pendle liquidity should be flagged even if total TVL passes the filter.

Pendle supported chains are read from the live Pendle Core markets API and chain IDs. Do not hardcode the scan to only Ethereum/Base/Arbitrum; current deployments include Ethereum, Optimism, BNB Chain, Sonic, HyperEVM, Mantle, Base, Arbitrum, Berachain, Monad, Katana, and Ink.

## Solana PT/YT Markets

Solana PT/YT markets are not Pendle EVM markets. Treat them as a separate indexed source and normalize them into the same Defimax opportunity shape only after a trusted feed provides real APY, TVL/liquidity, maturity, symbol, protocol, and source URL.

Current Solana PT/YT targets:

- Exponent Income: fixed-yield Income Token markets, normalized as `PT`.
- Exponent Farm: Yield Token markets, normalized as `YT`.
- RateX fixed/floating yield markets: normalize Principal Token markets as `PT` and Yield Token exposure as `YT` when the feed provides real market fields.

Useful official/user-facing URLs:

- `https://app.exponent.finance/income`
- `https://docs.exponent.finance/income`
- `https://docs.exponent.finance/farm`
- `https://app.rate-x.io/earn/fixed-yield?symbol=xSOL`
- `https://docs.rate-x.io/ratex/ratex-protocol/basic-concepts-of-yield-trading/pt-principal-token`

Automation note: some app pages are protected or rendered client-side, so do not rely on scraping them for production APY. Prefer an official API, an internal indexer, or an exported JSON snapshot. If the source does not expose real APY or liquidity, leave the market out of ranked live opportunities instead of using stale or guessed values.

Accepted indexed JSON shape:

```json
{
  "markets": [
    {
      "protocol": "exponent",
      "market": "USX",
      "positionType": "pt",
      "symbol": "PT-USX-01JUN26",
      "expiry": "2026-06-01",
      "apy": 6.13,
      "tvlUsd": 5000000,
      "liquidityUsd": 1100000,
      "stablecoin": true,
      "sourceUrl": "https://app.exponent.finance/income"
    }
  ]
}
```

Alternative field aliases accepted by `yield_monitor.py` include `type`, `tokenType`, `fixedApy`, `impliedApy`, `floatingApy`, `ytApy`, `marketTvlUsd`, `totalTvl`, `depthUsd`, `maturity`, `marketAddress`, and `mint`. If a feed uses decimal APY values, set `apyIsDecimal: true` or `apyFormat: "decimal"`.

## Protocol Network Catalogs

Use official sources when refreshing network support:

- Aave deployments: `https://aave.com/help/aave-101/accessing-aave`
- Aave Pool addresses: `https://github.com/aave-dao/aave-address-book`
- Pendle deployments: `https://docs.pendle.finance/cn/pendle-v2-dev/Deployments`
- Morpho addresses: `https://docs.morpho.org/get-started/resources/addresses/`
- Solana RPC: `https://solana.com/docs/rpc`
- Meteora DLMM docs: `https://docs.meteora.ag/developer-guide/guides/dlmm/overview`
- Meteora DLMM SDK functions: `https://docs.meteora.ag/developer-guide/guides/dlmm/typescript-sdk/sdk-functions`

Treat Solana as a separate data plane. It can be checked through Solana JSON-RPC, but wallet positions in Meteora DLMM/DAMM v2, Kamino, Drift, MarginFi, Jupiter, or other Solana protocols need protocol-specific account parsers or an indexer; EVM `eth_call` and ERC-20 balance reads do not apply.

Meteora DLMM notes:

- Mainnet DLMM program ID: `LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo`.
- Pool discovery can use `https://dlmm-api.meteora.ag/pair/all`.
- Wallet positions should use Meteora's DLMM SDK `getAllLbPairPositionsByUser(connection, userPubKey)` and then value the position by pool reserves/bin state, token decimals, fees, rewards, and active-bin range risk.

Ranking guidance:

- PT/fixed yield: rank by implied APY after filtering expiry, liquidity, and chain.
- YT/floating yield: rank separately by YT floating APY; never mix it with conservative fixed yield without a risk note.
- LP yield: rank by aggregated APY, but show underlying, swap fee, emissions, and points separately when available.
- Points markets: flag as optional upside, not guaranteed yield.
- External protocols: note collateral/borrowing integrations such as Aave, Morpho, Euler, and their LTV/borrow APY if present.

## Risk Checks

Always include practical risk flags:

- smart contract and protocol risk
- chain and bridge risk
- oracle risk
- stablecoin depeg risk
- reward token liquidity and emission sustainability
- impermanent loss for LP positions
- withdrawal lockups, caps, cooldowns, or maturity dates
- APY source quality: base yield versus incentives

Never imply that a high APY is safe because a protocol is popular. Prefer shortlists that a user can manually verify before depositing funds.
