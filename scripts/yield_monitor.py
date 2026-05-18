#!/usr/bin/env python3
"""Scan DeFi yield opportunities and produce a ranked report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFILLAMA_POOLS_URL = "https://yields.llama.fi/pools"
PENDLE_MARKETS_URL = "https://api-v2.pendle.finance/core/v2/markets/all"
USER_AGENT = "defimax/1.0"

CHAIN_NAMES = {
    1: "Ethereum",
    10: "Optimism",
    14: "Flare",
    25: "Cronos",
    50: "XDC",
    56: "BNB Chain",
    100: "Gnosis",
    130: "Unichain",
    143: "Monad",
    137: "Polygon",
    146: "Sonic",
    239: "TAC",
    250: "Fantom",
    252: "Fraxtal",
    324: "ZKsync Era",
    480: "World Chain",
    999: "HyperEVM",
    1088: "Metis",
    1135: "Lisk",
    1329: "Sei",
    1868: "Soneium",
    2741: "Abstract",
    8453: "Base",
    8217: "Kaia",
    9745: "Plasma",
    34443: "Mode",
    42161: "Arbitrum",
    42220: "Celo",
    42793: "Etherlink",
    43114: "Avalanche",
    5000: "Mantle",
    48900: "Zircuit",
    57073: "Ink",
    59144: "Linea",
    81457: "Blast",
    80094: "Berachain",
    98866: "Plume",
    200901: "Bitlayer",
    534352: "Scroll",
    747474: "Katana",
    1666600000: "Harmony",
    21000000: "Corn",
}

STABLE_HINTS = (
    "USD",
    "USDC",
    "USDT",
    "DAI",
    "FRAX",
    "USDE",
    "USDS",
    "USD0",
    "PYUSD",
    "GHO",
    "LUSD",
    "SUSD",
    "CRVUSD",
)

SELF_TEST_DATA = {
    "status": "success",
    "data": [
        {
            "pool": "stable-a",
            "project": "aave-v3",
            "chain": "Ethereum",
            "symbol": "USDC",
            "tvlUsd": 125000000,
            "apy": 5.2,
            "apyBase": 4.8,
            "apyReward": 0.4,
            "stablecoin": True,
            "ilRisk": "no",
            "exposure": "single",
            "outlier": False,
            "count": 300,
        },
        {
            "pool": "reward-b",
            "project": "new-farm",
            "chain": "Base",
            "symbol": "USDC-XYZ",
            "tvlUsd": 750000,
            "apy": 82.0,
            "apyBase": 2.0,
            "apyReward": 80.0,
            "stablecoin": False,
            "ilRisk": "yes",
            "exposure": "multi",
            "outlier": False,
            "count": 12,
        },
        {
            "pool": "outlier-c",
            "project": "bad-data",
            "chain": "Arbitrum",
            "symbol": "USDT",
            "tvlUsd": 9000000,
            "apy": 200.0,
            "stablecoin": True,
            "outlier": True,
        },
    ],
}

SELF_TEST_PENDLE_MARKETS = [
    {
        "name": "USDE",
        "address": "0xpendlemarket",
        "expiry": "2026-06-25T00:00:00.000Z",
        "pt": "1-0xpt",
        "yt": "1-0xyt",
        "chainId": 1,
        "categoryIds": ["stables"],
        "details": {
            "liquidity": 25_000_000,
            "totalTvl": 42_000_000,
            "underlyingApy": 0.065,
            "swapFeeApy": 0.004,
            "pendleApy": 0.011,
            "ytFloatingApy": 0.32,
            "impliedApy": 0.142,
            "aggregatedApy": 0.08,
            "ytRoi": 0.03,
            "ptRoi": 0.01,
        },
        "points": [{"key": "example-points", "pendleAsset": "basic", "value": 5}],
    }
]


def fetch_json(url: str, timeout: int = 25) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network error fetching {url}: {exc.reason}") from exc
    return json.loads(payload)


def load_defillama_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.self_test:
        return SELF_TEST_DATA
    if args.input_json:
        with open(args.input_json, "r", encoding="utf-8") as handle:
            return json.load(handle)
    if args.no_defillama:
        return {"data": []}
    return fetch_json(args.url)


def load_pendle_markets(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.no_pendle:
        return []
    if args.self_test:
        return SELF_TEST_PENDLE_MARKETS
    if args.pendle_input_json:
        with open(args.pendle_input_json, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return payload
        return payload.get("results", payload.get("data", payload))

    markets: list[dict[str, Any]] = []
    limit = min(max(args.pendle_page_size, 1), 100)
    skip = 0
    while len(markets) < args.pendle_max_markets:
        url = f"{args.pendle_url}?limit={limit}&skip={skip}"
        payload = fetch_json(url)
        batch = payload.get("results", payload.get("data", []))
        if not isinstance(batch, list) or not batch:
            break
        markets.extend(item for item in batch if isinstance(item, dict))
        total = safe_float(payload.get("total"))
        skip += limit
        if (total and skip >= total) or len(batch) < limit:
            break
    return markets[: args.pendle_max_markets]


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def normalized_set(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def il_risk(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() not in {"", "no", "none", "false", "0"}


def decimal_to_percent(value: Any) -> float:
    return safe_float(value) * 100.0


def chain_name(chain_id: Any) -> str:
    numeric = int(safe_float(chain_id)) if safe_float(chain_id) else 0
    return CHAIN_NAMES.get(numeric, f"chain-{chain_id}")


def looks_stable(symbol: str, categories: list[Any] | None = None) -> bool:
    if categories and any(str(item).lower() == "stables" for item in categories):
        return True
    upper = symbol.upper()
    return any(hint in upper for hint in STABLE_HINTS)


def is_active_expiry(expiry: Any) -> bool:
    if not expiry:
        return False
    now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return str(expiry) > now_iso


def short_expiry(expiry: Any) -> str:
    if not expiry:
        return ""
    return str(expiry).split("T", 1)[0]


def pool_apy(pool: dict[str, Any]) -> float:
    apy = safe_float(pool.get("apy"))
    if apy:
        return apy
    return safe_float(pool.get("apyBase")) + safe_float(pool.get("apyReward"))


def risk_flags(pool: dict[str, Any], apy: float, tvl: float, args: argparse.Namespace) -> list[str]:
    flags: list[str] = list(pool.get("extraFlags") or [])
    apy_reward = safe_float(pool.get("apyReward"))
    reward_share = apy_reward / apy if apy > 0 else 0.0
    exposure = str(pool.get("exposure") or "").lower()
    symbol = str(pool.get("symbol") or "")
    position_type = str(pool.get("positionType") or "pool").lower()

    if truthy(pool.get("outlier")):
        flags.append("outlier")
    if tvl < args.min_tvl_usd * 2:
        flags.append("near-min-tvl")
    multi_asset_symbol = "-" in symbol and position_type == "pool"
    if il_risk(pool.get("ilRisk")) or multi_asset_symbol or exposure not in {"", "single"}:
        flags.append("il-or-multi-asset")
    if reward_share >= 0.5:
        flags.append("reward-heavy")
    if apy >= args.high_apy_warning:
        flags.append("very-high-apy")
    if safe_float(pool.get("count")) and safe_float(pool.get("count")) < 30:
        flags.append("short-history")
    if not truthy(pool.get("stablecoin")):
        flags.append("volatile-asset")
    if position_type == "yt":
        flags.extend(["yield-token", "principal-not-redeemable", "floating-yield"])
    elif position_type == "pt":
        flags.append("fixed-maturity")
    elif position_type == "lp":
        flags.append("pendle-lp")
    liquidity = safe_float(pool.get("liquidityUsd"))
    if liquidity and liquidity < args.min_tvl_usd:
        flags.append("low-pendle-liquidity")
    return sorted(dict.fromkeys(flags))


def score_pool(pool: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    apy = pool_apy(pool)
    tvl = safe_float(pool.get("tvlUsd"))
    liquidity = safe_float(pool.get("liquidityUsd"))
    apy_base = safe_float(pool.get("apyBase"))
    apy_reward = safe_float(pool.get("apyReward"))
    reward_share = apy_reward / apy if apy > 0 else 0.0
    position_type = str(pool.get("positionType") or "pool").lower()

    tvl_score = min(30.0, max(0.0, math.log10(max(tvl, 1.0) / 10000.0) * 6.0))
    apy_score = min(42.0, max(0.0, apy) * 1.25)
    stable_bonus = 8.0 if truthy(pool.get("stablecoin")) else 0.0

    penalty = 0.0
    if truthy(pool.get("outlier")):
        penalty += 60.0
    if il_risk(pool.get("ilRisk")):
        penalty += 12.0
    if reward_share >= 0.5:
        penalty += min(24.0, reward_share * 24.0)
    if tvl < args.min_tvl_usd * 2:
        penalty += 6.0
    if safe_float(pool.get("count")) and safe_float(pool.get("count")) < 30:
        penalty += 6.0
    if position_type == "yt":
        penalty += 14.0
    elif position_type == "lp":
        penalty += 4.0
    if liquidity and liquidity < args.min_tvl_usd:
        penalty += 8.0

    if args.risk_profile == "conservative":
        if apy > 30:
            penalty += (apy - 30) * 0.6
        if not truthy(pool.get("stablecoin")):
            penalty += 10.0
    elif args.risk_profile == "aggressive":
        penalty *= 0.65

    score = round(max(0.0, apy_score + tvl_score + stable_bonus - penalty), 2)
    flags = risk_flags(pool, apy, tvl, args)

    return {
        "pool": str(pool.get("pool") or ""),
        "source": str(pool.get("source") or "defillama"),
        "positionType": position_type,
        "project": str(pool.get("project") or "unknown"),
        "chain": str(pool.get("chain") or "unknown"),
        "symbol": str(pool.get("symbol") or "unknown"),
        "poolMeta": pool.get("poolMeta"),
        "expiry": pool.get("expiry"),
        "liquidityUsd": round(liquidity, 2),
        "tvlUsd": round(tvl, 2),
        "apy": round(apy, 4),
        "apyBase": round(apy_base, 4),
        "apyReward": round(apy_reward, 4),
        "stablecoin": truthy(pool.get("stablecoin")),
        "outlier": truthy(pool.get("outlier")),
        "ilRisk": il_risk(pool.get("ilRisk")),
        "exposure": pool.get("exposure"),
        "score": score,
        "riskFlags": flags,
    }


def pendle_opportunities(markets: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for market in markets:
        if not is_active_expiry(market.get("expiry")):
            continue
        details = market.get("details") or {}
        if not isinstance(details, dict):
            continue

        name = str(market.get("name") or "unknown")
        market_address = str(market.get("address") or "")
        chain_id = market.get("chainId")
        chain = chain_name(chain_id)
        expiry = short_expiry(market.get("expiry"))
        tvl = safe_float(details.get("totalTvl"))
        liquidity = safe_float(details.get("liquidity"))
        categories = market.get("categoryIds") if isinstance(market.get("categoryIds"), list) else []
        stable = looks_stable(name, categories)
        points = market.get("points") if isinstance(market.get("points"), list) else []
        base_extra_flags = ["points"] if points else []

        common = {
            "source": "pendle-core",
            "project": "pendle",
            "chain": chain,
            "tvlUsd": tvl,
            "liquidityUsd": liquidity,
            "stablecoin": stable,
            "outlier": False,
            "ilRisk": False,
            "exposure": "single",
            "expiry": expiry,
        }

        implied_apy = decimal_to_percent(details.get("impliedApy"))
        if implied_apy > 0:
            opportunities.append(
                {
                    **common,
                    "pool": f"pendle:{chain_id}:{market_address}:pt",
                    "positionType": "pt",
                    "symbol": f"PT-{name}",
                    "poolMeta": f"PT fixed yield / maturity {expiry}",
                    "apy": implied_apy,
                    "apyBase": implied_apy,
                    "apyReward": 0.0,
                    "extraFlags": base_extra_flags,
                }
            )

        yt_apy = decimal_to_percent(details.get("ytFloatingApy"))
        if yt_apy > 0:
            opportunities.append(
                {
                    **common,
                    "pool": f"pendle:{chain_id}:{market_address}:yt",
                    "positionType": "yt",
                    "symbol": f"YT-{name}",
                    "poolMeta": f"YT floating yield / maturity {expiry}",
                    "apy": yt_apy,
                    "apyBase": yt_apy,
                    "apyReward": 0.0,
                    "extraFlags": base_extra_flags,
                }
            )

        lp_apy = decimal_to_percent(details.get("aggregatedApy"))
        if lp_apy > 0:
            base_apy = decimal_to_percent(details.get("underlyingApy")) + decimal_to_percent(
                details.get("swapFeeApy")
            )
            reward_apy = decimal_to_percent(details.get("pendleApy"))
            opportunities.append(
                {
                    **common,
                    "pool": f"pendle:{chain_id}:{market_address}:lp",
                    "positionType": "lp",
                    "symbol": f"LP-{name}",
                    "poolMeta": f"Pendle LP / maturity {expiry}",
                    "apy": lp_apy,
                    "apyBase": base_apy,
                    "apyReward": reward_apy,
                    "extraFlags": base_extra_flags,
                    "ilRisk": True,
                    "exposure": "pendle-lp",
                }
            )
    return opportunities


def passes_filters(item: dict[str, Any], args: argparse.Namespace) -> bool:
    chains = normalized_set(args.chains)
    projects = normalized_set(args.projects)
    symbols = normalized_set(args.symbols)
    exclude_projects = normalized_set(args.exclude_projects)
    position_types = normalized_set(args.position_types)

    if item["apy"] < args.min_apy:
        return False
    if args.max_apy is not None and item["apy"] > args.max_apy:
        return False
    if item["tvlUsd"] < args.min_tvl_usd:
        return False
    if args.stable_only and not item["stablecoin"]:
        return False
    if item["outlier"] and not args.include_outliers:
        return False
    if chains and item["chain"].lower() not in chains:
        return False
    if projects and item["project"].lower() not in projects:
        return False
    if item["project"].lower() in exclude_projects:
        return False
    if position_types and item["positionType"].lower() not in position_types:
        return False
    if symbols:
        symbol = item["symbol"].lower()
        if not any(token in symbol for token in symbols):
            return False
    return True


def rank_pools(
    raw: dict[str, Any], pendle_markets: list[dict[str, Any]], args: argparse.Namespace
) -> list[dict[str, Any]]:
    pools = raw.get("data", raw)
    if not isinstance(pools, list):
        raise RuntimeError("expected DefiLlama payload with a data list")
    normalized_pools: list[dict[str, Any]] = []
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        if not args.keep_defillama_pendle and str(pool.get("project") or "").lower() == "pendle":
            continue
        normalized_pools.append({**pool, "source": "defillama", "positionType": "pool"})

    normalized_pools.extend(pendle_opportunities(pendle_markets, args))
    ranked = [score_pool(pool, args) for pool in normalized_pools]
    filtered = [item for item in ranked if passes_filters(item, args)]
    filtered.sort(key=lambda item: (item["score"], item["apy"], item["tvlUsd"]), reverse=True)
    return filtered[: args.limit]


def load_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    state_path = Path(path).expanduser()
    if not state_path.exists():
        return {}
    with open(state_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_state(path: str | None, opportunities: list[dict[str, Any]]) -> None:
    if not path:
        return
    state_path = Path(path).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "pools": {
            item["pool"]: {
                "apy": item["apy"],
                "tvlUsd": item["tvlUsd"],
                "score": item["score"],
                "riskFlags": item["riskFlags"],
            }
            for item in opportunities
            if item.get("pool")
        },
    }
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def diff_state(
    previous: dict[str, Any], opportunities: list[dict[str, Any]], args: argparse.Namespace
) -> list[dict[str, Any]]:
    previous_pools = previous.get("pools", {}) if isinstance(previous, dict) else {}
    if not previous_pools and not args.emit_initial_alerts:
        return []
    events: list[dict[str, Any]] = []
    for item in opportunities:
        pool_id = item.get("pool")
        if not pool_id:
            continue
        old = previous_pools.get(pool_id)
        if not old:
            events.append({"type": "new", "pool": pool_id, "opportunity": item})
            continue
        old_apy = safe_float(old.get("apy"))
        apy_delta = item["apy"] - old_apy
        old_flags = set(old.get("riskFlags") or [])
        new_flags = set(item.get("riskFlags") or [])
        if abs(apy_delta) >= args.alert_apy_change:
            events.append(
                {
                    "type": "apy-change",
                    "pool": pool_id,
                    "previousApy": round(old_apy, 4),
                    "currentApy": item["apy"],
                    "delta": round(apy_delta, 4),
                    "opportunity": item,
                }
            )
        elif old_flags != new_flags:
            events.append(
                {
                    "type": "risk-flags-change",
                    "pool": pool_id,
                    "previousFlags": sorted(old_flags),
                    "currentFlags": sorted(new_flags),
                    "opportunity": item,
                }
            )
    return events


def money(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def table_cell(value: Any) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").strip()


def pool_label(item: dict[str, Any]) -> str:
    meta = item.get("poolMeta")
    if meta:
        return table_cell(meta)
    pool_id = str(item.get("pool") or "")
    if len(pool_id) > 12:
        return f"{pool_id[:6]}...{pool_id[-4:]}"
    return pool_id or "n/a"


def format_markdown(
    opportunities: list[dict[str, Any]], events: list[dict[str, Any]], args: argparse.Namespace
) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"Defimax Yield Monitor | {now}",
        "",
        (
            f"Filters: risk={args.risk_profile}, min_tvl={money(args.min_tvl_usd)}, "
            f"min_apy={args.min_apy:.2f}%, stable_only={args.stable_only}, "
            f"position_types={args.position_types or 'all'}"
        ),
        "",
    ]
    if not opportunities:
        lines.append("No opportunities passed the current filters.")
        return "\n".join(lines)

    lines.extend(
        [
            "| # | Score | Source | Type | Project | Chain | Symbol | Expiry | Pool/Meta | APY | Base/Reward | TVL | Flags |",
            "|---:|---:|---|---|---|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for index, item in enumerate(opportunities, start=1):
        flags = ", ".join(item["riskFlags"]) if item["riskFlags"] else "none"
        lines.append(
            "| {idx} | {score:.2f} | {source} | {ptype} | {project} | {chain} | {symbol} | "
            "{expiry} | {pool} | {apy:.2f}% | "
            "{base:.2f}%/{reward:.2f}% | {tvl} | {flags} |".format(
                idx=index,
                score=item["score"],
                source=table_cell(item["source"]),
                ptype=table_cell(item["positionType"].upper()),
                project=table_cell(item["project"]),
                chain=table_cell(item["chain"]),
                symbol=table_cell(item["symbol"]),
                expiry=table_cell(item.get("expiry")),
                pool=pool_label(item),
                apy=item["apy"],
                base=item["apyBase"],
                reward=item["apyReward"],
                tvl=money(item["tvlUsd"]),
                flags=flags,
            )
        )

    if events:
        lines.extend(["", "Alert events:"])
        for event in events[: args.limit]:
            item = event["opportunity"]
            if event["type"] == "new":
                lines.append(
                    f"- New: {item['positionType'].upper()} {item['project']} {item['symbol']} on {item['chain']} at {item['apy']:.2f}% APY"
                )
            elif event["type"] == "apy-change":
                lines.append(
                    "- APY change: {project} {symbol} on {chain} "
                    "{previous:.2f}% -> {current:.2f}% ({delta:+.2f} pp)".format(
                        project=item["project"],
                        symbol=item["symbol"],
                        chain=item["chain"],
                        previous=event["previousApy"],
                        current=event["currentApy"],
                        delta=event["delta"],
                    )
                )
            elif event["type"] == "risk-flags-change":
                lines.append(
                    f"- Risk flags changed: {item['project']} {item['symbol']} on {item['chain']}"
                )

    lines.extend(
        [
            "",
            "Check before action: official app URL, contract addresses, lockups, withdrawal caps, bridge risk, oracle/depeg risk, reward token liquidity, and whether APY is base yield or incentives.",
        ]
    )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank DeFi yield opportunities from DefiLlama and Pendle.")
    parser.add_argument("--url", default=os.environ.get("DEFILLAMA_YIELDS_URL", DEFILLAMA_POOLS_URL))
    parser.add_argument("--pendle-url", default=os.environ.get("PENDLE_MARKETS_URL", PENDLE_MARKETS_URL))
    parser.add_argument("--input-json", help="Read a saved DefiLlama pools payload instead of fetching.")
    parser.add_argument("--pendle-input-json", help="Read a saved Pendle markets payload instead of fetching.")
    parser.add_argument("--self-test", action="store_true", help="Run against built-in fixture data.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--risk-profile", choices=["conservative", "balanced", "aggressive"], default="balanced")
    parser.add_argument("--min-tvl-usd", type=float, default=1_000_000)
    parser.add_argument("--min-apy", type=float, default=0.0)
    parser.add_argument("--max-apy", type=float)
    parser.add_argument("--high-apy-warning", type=float, default=50.0)
    parser.add_argument("--stable-only", action="store_true")
    parser.add_argument("--include-outliers", action="store_true")
    parser.add_argument("--chains", help="Comma-separated exact chain names, e.g. Ethereum,Base,Arbitrum.")
    parser.add_argument("--projects", help="Comma-separated exact DefiLlama project slugs.")
    parser.add_argument("--exclude-projects", help="Comma-separated project slugs to exclude.")
    parser.add_argument("--symbols", help="Comma-separated symbol substrings, e.g. USDC,USDT,ETH.")
    parser.add_argument("--position-types", help="Comma-separated types: pool,pt,yt,lp.")
    parser.add_argument("--no-defillama", action="store_true", help="Disable DefiLlama source.")
    parser.add_argument("--no-pendle", action="store_true", help="Disable native Pendle PT/YT/LP source.")
    parser.add_argument("--keep-defillama-pendle", action="store_true", help="Keep Pendle rows from DefiLlama too.")
    parser.add_argument("--pendle-page-size", type=int, default=100)
    parser.add_argument("--pendle-max-markets", type=int, default=600)
    parser.add_argument("--state", help="Path to JSON state file for recurring alert diffs.")
    parser.add_argument("--no-write-state", action="store_true")
    parser.add_argument("--emit-initial-alerts", action="store_true")
    parser.add_argument("--alert-apy-change", type=float, default=1.0, help="Percentage-point APY move to alert.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        raw = load_defillama_input(args)
        pendle_markets = load_pendle_markets(args)
        previous = load_state(args.state)
        opportunities = rank_pools(raw, pendle_markets, args)
        events = diff_state(previous, opportunities, args)
        if args.state and not args.no_write_state:
            write_state(args.state, opportunities)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "filters": {
                        "riskProfile": args.risk_profile,
                        "minTvlUsd": args.min_tvl_usd,
                        "minApy": args.min_apy,
                        "stableOnly": args.stable_only,
                        "positionTypes": args.position_types,
                        "defillama": not args.no_defillama,
                        "pendle": not args.no_pendle,
                        "limit": args.limit,
                    },
                    "opportunities": opportunities,
                    "alertEvents": events,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(format_markdown(opportunities, events, args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
