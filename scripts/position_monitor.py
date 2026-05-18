#!/usr/bin/env python3
"""Monitor configured PT/YT lending loops, alerts, and guarded action plans."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yield_monitor


DEFAULT_CONFIG = "~/.config/defimax/config.json"
DEFAULT_DB = "~/.cache/defimax/history.sqlite"
MORPHO_GRAPHQL_URL = "https://blue-api.morpho.org/graphql"
AAVE_GET_USER_ACCOUNT_DATA_SELECTOR = "bf92857c"
ERC20_BALANCE_OF_SELECTOR = "70a08231"
ERC20_DECIMALS_SELECTOR = "313ce567"
SECONDS_PER_YEAR = 31_536_000
METEORA_DLMM_PROGRAM_ID = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
METEORA_DLMM_PAIRS_API = "https://dlmm-api.meteora.ag/pair/all"
SOLANA_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SOLANA_DEFI_ADAPTER_TARGETS = {
    "meteora-dlmm": {
        "status": "adapter-required",
        "program_id": METEORA_DLMM_PROGRAM_ID,
        "positions_method": "Meteora DLMM SDK getAllLbPairPositionsByUser(connection, userPubKey)",
        "pairs_api": METEORA_DLMM_PAIRS_API,
    },
    "meteora-damm-v2": {"status": "adapter-required"},
    "kamino": {"status": "adapter-required"},
    "drift": {"status": "adapter-required"},
    "marginfi": {"status": "adapter-required"},
    "jupiter": {"status": "adapter-required"},
}

PUBLIC_RPC_BY_CHAIN_ID = {
    1: ["https://eth.llamarpc.com", "https://ethereum-rpc.publicnode.com"],
    10: ["https://mainnet.optimism.io", "https://optimism-rpc.publicnode.com"],
    14: ["https://flare-api.flare.network/ext/C/rpc", "https://flare-rpc.publicnode.com"],
    25: ["https://evm.cronos.org", "https://cronos-evm-rpc.publicnode.com"],
    50: ["https://rpc.xinfin.network"],
    56: ["https://bsc-dataseed.binance.org", "https://binance.llamarpc.com"],
    100: ["https://rpc.gnosischain.com", "https://gnosis-rpc.publicnode.com"],
    130: ["https://mainnet.unichain.org", "https://unichain-rpc.publicnode.com"],
    143: ["https://rpc.monad.xyz"],
    137: ["https://polygon-rpc.com", "https://polygon-bor-rpc.publicnode.com"],
    146: ["https://rpc.soniclabs.com"],
    239: ["https://rpc.tac.build"],
    250: ["https://rpcapi.fantom.network", "https://rpc.ftm.tools"],
    252: ["https://rpc.frax.com"],
    324: ["https://mainnet.era.zksync.io", "https://zksync-era-rpc.publicnode.com"],
    480: ["https://worldchain-mainnet.g.alchemy.com/public"],
    999: ["https://rpc.hyperliquid.xyz/evm"],
    1088: ["https://andromeda.metis.io/?owner=1088", "https://metis-rpc.publicnode.com"],
    1135: ["https://rpc.api.lisk.com"],
    1329: ["https://evm-rpc.sei-apis.com"],
    1868: ["https://rpc.soneium.org"],
    2741: ["https://api.mainnet.abs.xyz"],
    5000: ["https://rpc.mantle.xyz", "https://mantle-rpc.publicnode.com"],
    8217: ["https://public-en.node.kaia.io"],
    9745: ["https://rpc.plasma.to"],
    8453: ["https://mainnet.base.org", "https://base.llamarpc.com", "https://base-rpc.publicnode.com"],
    34443: ["https://mainnet.mode.network"],
    42161: ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com"],
    42220: ["https://forno.celo.org", "https://celo-rpc.publicnode.com"],
    42793: ["https://node.mainnet.etherlink.com"],
    43114: ["https://api.avax.network/ext/bc/C/rpc", "https://avalanche-c-chain-rpc.publicnode.com"],
    48900: ["https://mainnet.zircuit.com", "https://zircuit1-mainnet.liquify.com"],
    59144: ["https://rpc.linea.build", "https://linea-rpc.publicnode.com"],
    81457: ["https://rpc.blast.io", "https://blast-rpc.publicnode.com"],
    98866: ["https://rpc.plume.org"],
    200901: ["https://rpc.bitlayer.org"],
    534352: ["https://rpc.scroll.io", "https://scroll-rpc.publicnode.com"],
    57073: ["https://rpc-gel.inkonchain.com"],
    80094: ["https://rpc.berachain.com"],
    747474: ["https://rpc.katana.network"],
    1666600000: ["https://api.harmony.one"],
    21000000: ["https://mainnet.corn-rpc.com"],
}

SOLANA_RPC_URLS = ["https://api.mainnet.solana.com", "https://api.mainnet-beta.solana.com"]

DEFAULT_CHAIN_CONFIGS = {
    "ethereum": {"chain_id": 1, "rpc_url_env": "ETH_RPC_URL", "aave_pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2", "aave_base_decimals": 8},
    "optimism": {"chain_id": 10, "rpc_url_env": "OPTIMISM_RPC_URL", "aave_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "aave_base_decimals": 8},
    "flare": {"chain_id": 14, "rpc_url_env": "FLARE_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "cronos": {"chain_id": 25, "rpc_url_env": "CRONOS_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "xdc": {"chain_id": 50, "rpc_url_env": "XDC_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "bnb": {"chain_id": 56, "rpc_url_env": "BNB_RPC_URL", "aave_pool": "0x6807dc923806fE8Fd134338EABCA509979a7e0cB", "aave_base_decimals": 8},
    "gnosis": {"chain_id": 100, "rpc_url_env": "GNOSIS_RPC_URL", "aave_pool": "0xb50201558B00496A145fE76f7424749556E326D8", "aave_base_decimals": 8},
    "unichain": {"chain_id": 130, "rpc_url_env": "UNICHAIN_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "monad": {"chain_id": 143, "rpc_url_env": "MONAD_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "polygon": {"chain_id": 137, "rpc_url_env": "POLYGON_RPC_URL", "aave_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "aave_base_decimals": 8},
    "sonic": {"chain_id": 146, "rpc_url_env": "SONIC_RPC_URL", "aave_pool": "0x5362dBb1e601abF3a4c14c22ffEdA64042E5eAA3", "aave_base_decimals": 8},
    "tac": {"chain_id": 239, "rpc_url_env": "TAC_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "fantom": {"chain_id": 250, "rpc_url_env": "FANTOM_RPC_URL", "aave_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "aave_base_decimals": 8},
    "fraxtal": {"chain_id": 252, "rpc_url_env": "FRAXTAL_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "zksync": {"chain_id": 324, "rpc_url_env": "ZKSYNC_RPC_URL", "aave_pool": "0x78e30497a3c7527d953c6B1E3541b021A98Ac43c", "aave_base_decimals": 8},
    "worldchain": {"chain_id": 480, "rpc_url_env": "WORLDCHAIN_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "hyperevm": {"chain_id": 999, "rpc_url_env": "HYPEREVM_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "metis": {"chain_id": 1088, "rpc_url_env": "METIS_RPC_URL", "aave_pool": "0x90df02551bB792286e8D4f13E0e357b4Bf1D6a57", "aave_base_decimals": 8},
    "lisk": {"chain_id": 1135, "rpc_url_env": "LISK_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "sei": {"chain_id": 1329, "rpc_url_env": "SEI_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "soneium": {"chain_id": 1868, "rpc_url_env": "SONEIUM_RPC_URL", "aave_pool": "0xDd3d7A7d03D9fD9ef45f3E587287922eF65CA38B", "aave_base_decimals": 8},
    "abstract": {"chain_id": 2741, "rpc_url_env": "ABSTRACT_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "mantle": {"chain_id": 5000, "rpc_url_env": "MANTLE_RPC_URL", "aave_pool": "0x458F293454fE0d67EC0655f3672301301DD51422", "aave_base_decimals": 8},
    "kaia": {"chain_id": 8217, "rpc_url_env": "KAIA_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "plasma": {"chain_id": 9745, "rpc_url_env": "PLASMA_RPC_URL", "aave_pool": "0x925a2A7214Ed92428B5b1B090F80b25700095e12", "aave_base_decimals": 8},
    "base": {"chain_id": 8453, "rpc_url_env": "BASE_RPC_URL", "aave_pool": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5", "aave_base_decimals": 8},
    "mode": {"chain_id": 34443, "rpc_url_env": "MODE_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "arbitrum": {"chain_id": 42161, "rpc_url_env": "ARBITRUM_RPC_URL", "aave_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "aave_base_decimals": 8},
    "celo": {"chain_id": 42220, "rpc_url_env": "CELO_RPC_URL", "aave_pool": "0x3E59A31363E2ad014dcbc521c4a0d5757d9f3402", "aave_base_decimals": 8},
    "etherlink": {"chain_id": 42793, "rpc_url_env": "ETHERLINK_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "avalanche": {"chain_id": 43114, "rpc_url_env": "AVALANCHE_RPC_URL", "aave_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "aave_base_decimals": 8},
    "zircuit": {"chain_id": 48900, "rpc_url_env": "ZIRCUIT_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "linea": {"chain_id": 59144, "rpc_url_env": "LINEA_RPC_URL", "aave_pool": "0xc47b8C00b0f69a36fa203Ffeac0334874574a8Ac", "aave_base_decimals": 8},
    "blast": {"chain_id": 81457, "rpc_url_env": "BLAST_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "plume": {"chain_id": 98866, "rpc_url_env": "PLUME_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "bitlayer": {"chain_id": 200901, "rpc_url_env": "BITLAYER_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "scroll": {"chain_id": 534352, "rpc_url_env": "SCROLL_RPC_URL", "aave_pool": "0x11fCfe756c05AD438e312a7fd934381537D3cFfe", "aave_base_decimals": 8},
    "ink": {"chain_id": 57073, "rpc_url_env": "INK_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "berachain": {"chain_id": 80094, "rpc_url_env": "BERACHAIN_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "katana": {"chain_id": 747474, "rpc_url_env": "KATANA_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "harmony": {"chain_id": 1666600000, "rpc_url_env": "HARMONY_RPC_URL", "aave_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "aave_base_decimals": 8},
    "corn": {"chain_id": 21000000, "rpc_url_env": "CORN_RPC_URL", "aave_pool": "", "aave_base_decimals": 8},
    "solana": {"family": "solana", "chain_id": "solana-mainnet", "rpc_url_env": "SOLANA_RPC_URL", "aave_pool": "", "aave_base_decimals": 0},
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def expand_path(path: str | None) -> Path:
    return Path(path or DEFAULT_CONFIG).expanduser()


def load_json(path: str | Path) -> dict[str, Any]:
    with open(Path(path).expanduser(), "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def env_value(name_or_value: str | None) -> str | None:
    if not name_or_value:
        return None
    if name_or_value.startswith("env:"):
        return os.environ.get(name_or_value.split(":", 1)[1])
    return os.environ.get(name_or_value, name_or_value)


def is_valid_address(address: str | None) -> bool:
    if not address:
        return False
    clean = str(address).lower().replace("0x", "")
    return len(clean) == 40 and all(ch in "0123456789abcdef" for ch in clean)


def is_valid_solana_address(address: str | None) -> bool:
    if not address:
        return False
    clean = str(address).strip()
    return 32 <= len(clean) <= 44 and all(ch in SOLANA_BASE58_ALPHABET for ch in clean)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def evm_chain_id(chain: dict[str, Any]) -> int | None:
    if chain.get("family") and str(chain.get("family")).lower() != "evm":
        return None
    raw = chain.get("chain_id")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def wad_to_decimal(value: Any) -> float:
    raw = safe_float(value)
    if raw > 1_000_000:
        return raw / 1e18
    return raw


def money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.2f}"


def example_config() -> dict[str, Any]:
    return {
        "version": 1,
        "wallet": "0x0000000000000000000000000000000000000000",
        "mode": "monitor-only",
        "schedule": "6h",
        "database": DEFAULT_DB,
        "chains": DEFAULT_CHAIN_CONFIGS,
        "risk": {
            "min_health_factor": 1.30,
            "critical_health_factor": 1.12,
            "max_ltv": 0.70,
            "max_borrow_apy": 0.12,
            "days_to_maturity_warning": 10,
            "max_slippage_bps": 50,
            "min_liquidity_usd": 1_000_000,
        },
        "alerts": {
            "min_interval_hours": 6,
            "telegram": {
                "enabled": False,
                "bot_token_env": "TELEGRAM_BOT_TOKEN",
                "chat_id_env": "TELEGRAM_CHAT_ID",
            },
            "discord": {
                "enabled": False,
                "webhook_url_env": "DISCORD_WEBHOOK_URL",
            },
        },
        "execution": {
            "mode": "draft-only",
            "walletconnect_skill": "walletconnect-mqc",
            "require_chat_confirmation": True,
            "allow_unattended_signing": False,
        },
        "solana_defi": {
            "adapter_status": "rpc-ready-adapter-required",
            "enabled_protocols": [
                "meteora-dlmm",
                "meteora-damm-v2",
                "kamino",
                "drift",
                "marginfi",
                "jupiter",
            ],
            "meteora": {
                "dlmm_program_id": METEORA_DLMM_PROGRAM_ID,
                "dlmm_pairs_api": METEORA_DLMM_PAIRS_API,
            },
        },
        "loops": [
            {
                "name": "PT apyUSD loop on Morpho",
                "enabled": True,
                "protocol": "morpho",
                "chain": "ethereum",
                "position_type": "pt-loop",
                "pendle_symbol": "PT-apyUSD",
                "pendle_market": "",
                "morpho_market_unique_key": "",
                "morpho_market_id": "",
                "value_source": "live-first",
                "collateral_usd": 10_000,
                "debt_usd": 6_500,
                "equity_usd": 3_500,
                "target_ltv": 0.65,
                "liquidation_threshold": 0.86,
                "loop_iterations": 3,
                "borrow_apy": 0.07,
                "pt_apy": 0.18,
                "slippage_bps": 30,
                "gas_usd": 25,
                "depth_liquidity_usd": 500_000,
            },
            {
                "name": "Aave health monitor",
                "enabled": False,
                "protocol": "aave-v3",
                "chain": "ethereum",
                "position_type": "health-monitor",
                "collateral_usd": 0,
                "debt_usd": 0,
                "equity_usd": 0,
                "target_ltv": 0.60,
                "liquidation_threshold": 0.80,
                "borrow_apy": 0.05,
                "pt_apy": 0.10,
            },
        ],
    }


def prompt_value(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def run_wizard(args: argparse.Namespace) -> int:
    config_path = expand_path(args.config)
    if args.write_example:
        write_json(config_path, example_config())
        print(f"Example config written to {config_path}")
        return 0

    print("Defimax setup")
    print("No seed phrase or private key is needed. Use public wallet/RPC data only.")
    cfg = example_config()
    cfg["wallet"] = prompt_value("Wallet address", cfg["wallet"])
    cfg["schedule"] = prompt_value("Schedule: 6h or daily", cfg["schedule"])
    cfg["risk"]["min_health_factor"] = safe_float(
        prompt_value("Minimum health factor alert", str(cfg["risk"]["min_health_factor"])),
        cfg["risk"]["min_health_factor"],
    )
    cfg["risk"]["critical_health_factor"] = safe_float(
        prompt_value("Critical health factor alert", str(cfg["risk"]["critical_health_factor"])),
        cfg["risk"]["critical_health_factor"],
    )
    cfg["alerts"]["telegram"]["enabled"] = prompt_value("Enable Telegram alerts? true/false", "false").lower() == "true"
    cfg["alerts"]["discord"]["enabled"] = prompt_value("Enable Discord webhook alerts? true/false", "false").lower() == "true"

    first = cfg["loops"][0]
    first["name"] = prompt_value("First loop name", first["name"])
    first["protocol"] = prompt_value("Protocol: morpho, aave-v3, euler-v2, manual", first["protocol"])
    first["chain"] = prompt_value("Chain key", first["chain"])
    first["pendle_symbol"] = prompt_value("Pendle symbol, e.g. PT-apyUSD", first["pendle_symbol"])
    first["value_source"] = prompt_value("Value source: live-first or manual", first["value_source"])
    if first["protocol"].lower() == "morpho":
        first["morpho_market_unique_key"] = prompt_value(
            "Morpho market unique key / market id", first["morpho_market_unique_key"]
        )
        first["morpho_market_id"] = first["morpho_market_unique_key"]
    if first["protocol"].lower() == "aave-v3":
        chain = cfg["chains"].setdefault(first["chain"], {})
        chain["rpc_url_env"] = prompt_value("RPC env var for this chain", chain.get("rpc_url_env", "ETH_RPC_URL"))
        chain["aave_pool"] = prompt_value("Aave V3 Pool address", chain.get("aave_pool", ""))
    first["collateral_usd"] = safe_float(prompt_value("Collateral USD", str(first["collateral_usd"])))
    first["debt_usd"] = safe_float(prompt_value("Debt USD", str(first["debt_usd"])))
    first["equity_usd"] = max(first["collateral_usd"] - first["debt_usd"], 0.0)
    first["target_ltv"] = safe_float(prompt_value("Target LTV, e.g. 0.65", str(first["target_ltv"])))
    first["liquidation_threshold"] = safe_float(
        prompt_value("Liquidation threshold, e.g. 0.86", str(first["liquidation_threshold"]))
    )
    first["borrow_apy"] = safe_float(prompt_value("Borrow APY as decimal, e.g. 0.07", str(first["borrow_apy"])))
    first["pt_apy"] = safe_float(prompt_value("PT/YT yield APY as decimal", str(first["pt_apy"])))

    write_json(config_path, cfg)
    print(f"Config written to {config_path}")
    return 0


def init_db(db_path: str | Path) -> sqlite3.Connection:
    path = Path(str(db_path)).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS position_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            name TEXT NOT NULL,
            protocol TEXT,
            chain TEXT,
            severity TEXT,
            health_factor REAL,
            ltv REAL,
            net_apy REAL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            name TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            delivered INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tx_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            name TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def graphql_post(url: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "defimax/1.0"},
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_morpho_market(market_id: str, chain_id: int, endpoint: str = MORPHO_GRAPHQL_URL) -> dict[str, Any]:
    query = """
    query Market($marketId: String!, $chainId: Int!) {
      marketById(marketId: $marketId, chainId: $chainId) {
        marketId
        lltv
        loanAsset { address symbol decimals }
        collateralAsset { address symbol decimals }
        state {
          borrowApy
          netBorrowApy
          supplyApy
          netSupplyApy
          borrowAssetsUsd
          supplyAssetsUsd
          collateralAssetsUsd
          utilization
          liquidityAssetsUsd
        }
      }
    }
    """
    result = graphql_post(endpoint, query, {"marketId": market_id, "chainId": chain_id})
    return ((result.get("data") or {}).get("marketById") or {})


def fetch_morpho_position(
    user_address: str, market_unique_key: str, chain_id: int, endpoint: str = MORPHO_GRAPHQL_URL
) -> dict[str, Any]:
    query = """
    query Position($userAddress: String!, $marketUniqueKey: String!, $chainId: Int!) {
      marketPosition(userAddress: $userAddress, marketUniqueKey: $marketUniqueKey, chainId: $chainId) {
        healthFactor
        priceVariationToLiquidationPrice
        market {
          marketId
          lltv
          loanAsset { address symbol decimals }
          collateralAsset { address symbol decimals }
          state {
            borrowApy
            netBorrowApy
            borrowAssetsUsd
            collateralAssetsUsd
            liquidityAssetsUsd
            utilization
          }
        }
        state {
          collateralUsd
          borrowAssetsUsd
          supplyAssetsUsd
          marginUsd
        }
      }
    }
    """
    result = graphql_post(
        endpoint,
        query,
        {"userAddress": user_address, "marketUniqueKey": market_unique_key, "chainId": chain_id},
    )
    return ((result.get("data") or {}).get("marketPosition") or {})


def fetch_morpho_user(address: str, chain_id: int, endpoint: str = MORPHO_GRAPHQL_URL) -> dict[str, Any]:
    query = """
    query User($address: String!, $chainId: Int!) {
      userByAddress(address: $address, chainId: $chainId) {
        address
        marketPositions {
          healthFactor
          priceVariationToLiquidationPrice
          market { marketId lltv }
          state {
            collateralUsd
            borrowAssetsUsd
            supplyAssetsUsd
            marginUsd
          }
        }
        vaultPositions {
          vault { address name }
          assets
          assetsUsd
          shares
        }
      }
    }
    """
    result = graphql_post(endpoint, query, {"address": address, "chainId": chain_id})
    return ((result.get("data") or {}).get("userByAddress") or {})


def encode_address_arg(address: str) -> str:
    clean = address.lower().replace("0x", "")
    if len(clean) != 40:
        raise ValueError(f"invalid EVM address: {address}")
    return clean.rjust(64, "0")


def rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    req = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "defimax/1.0"},
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result.get("result")


def rpc_chain_id(rpc_url: str) -> int | None:
    try:
        raw = rpc_call(rpc_url, "eth_chainId", [])
    except Exception:
        return None
    if isinstance(raw, str) and raw.startswith("0x"):
        return int(raw, 16)
    return int(safe_float(raw)) if raw is not None else None


def rpc_works_for_chain(rpc_url: str, chain_id: int) -> bool:
    actual = rpc_chain_id(rpc_url)
    return actual == chain_id


def solana_rpc_works(rpc_url: str) -> bool:
    try:
        result = rpc_call(rpc_url, "getHealth", [])
    except Exception:
        return False
    return result == "ok"


def solana_rpc_url(config: dict[str, Any]) -> str | None:
    chain = (config.get("chains") or {}).get("solana", {})
    candidates = []
    rpc = os.environ.get(str(chain.get("rpc_url_env"))) if chain.get("rpc_url_env") else None
    if not rpc:
        rpc = env_value(chain.get("rpc_url"))
    if rpc:
        candidates.append(rpc)
    candidates.extend(SOLANA_RPC_URLS)
    for candidate in dict.fromkeys(candidates):
        if solana_rpc_works(candidate):
            return candidate
    return candidates[0] if candidates else None


def aave_user_account_data(rpc_url: str, pool: str, user: str) -> dict[str, Any]:
    data = "0x" + AAVE_GET_USER_ACCOUNT_DATA_SELECTOR + encode_address_arg(user)
    raw = rpc_call(rpc_url, "eth_call", [{"to": pool, "data": data}, "latest"])
    if not raw or raw == "0x":
        raise RuntimeError("empty Aave getUserAccountData response")
    words = [int(raw[2 + i : 2 + i + 64], 16) for i in range(0, len(raw[2:]), 64)]
    if len(words) < 6:
        raise RuntimeError("short Aave getUserAccountData response")
    return {
        "totalCollateralBase": words[0],
        "totalDebtBase": words[1],
        "availableBorrowsBase": words[2],
        "currentLiquidationThresholdBps": words[3],
        "ltvBps": words[4],
        "healthFactor": words[5] / 1e18 if words[5] else None,
    }


def parse_token_id(token_id: str | None) -> tuple[int, str] | None:
    if not token_id:
        return None
    raw = str(token_id)
    if "-" not in raw:
        return None
    chain_id, address = raw.split("-", 1)
    if not is_valid_address(address):
        return None
    if not chain_id.isdigit():
        return None
    return int(chain_id), "0x" + address.lower().replace("0x", "")


def rpc_url_for_chain(config: dict[str, Any], chain_id: int) -> str | None:
    candidates: list[str] = []
    for chain in (config.get("chains") or {}).values():
        if evm_chain_id(chain) != chain_id:
            continue
        rpc = os.environ.get(str(chain.get("rpc_url_env"))) if chain.get("rpc_url_env") else None
        if not rpc:
            rpc = env_value(chain.get("rpc_url"))
        if rpc:
            candidates.append(rpc)
    public = PUBLIC_RPC_BY_CHAIN_ID.get(chain_id, [])
    if isinstance(public, str):
        candidates.append(public)
    else:
        candidates.extend(public)
    for candidate in dict.fromkeys(candidates):
        if rpc_works_for_chain(candidate, chain_id):
            return candidate
    return candidates[0] if candidates else None


def erc20_balance_of(rpc_url: str, token: str, owner: str) -> int:
    data = "0x" + ERC20_BALANCE_OF_SELECTOR + encode_address_arg(owner)
    raw = rpc_call(rpc_url, "eth_call", [{"to": token, "data": data}, "latest"])
    if not raw or raw == "0x":
        return 0
    return int(raw, 16)


def erc20_decimals(rpc_url: str, token: str) -> int | None:
    try:
        raw = rpc_call(rpc_url, "eth_call", [{"to": token, "data": "0x" + ERC20_DECIMALS_SELECTOR}, "latest"])
    except Exception:
        return None
    if not raw or raw == "0x":
        return None
    return int(raw, 16)


def apply_morpho_live_values(enriched: dict[str, Any], position: dict[str, Any]) -> None:
    state = position.get("state") or {}
    market = position.get("market") or {}
    market_state = market.get("state") or {}
    collateral_usd = safe_float(state.get("collateralUsd"))
    debt_usd = safe_float(state.get("borrowAssetsUsd"))
    margin_usd = safe_float(state.get("marginUsd"))
    if collateral_usd:
        enriched["collateral_usd"] = collateral_usd
    if debt_usd:
        enriched["debt_usd"] = debt_usd
    if margin_usd:
        enriched["equity_usd"] = margin_usd
    elif collateral_usd or debt_usd:
        enriched["equity_usd"] = max(collateral_usd - debt_usd, 0.0)
    if market.get("lltv") is not None:
        enriched["liquidation_threshold"] = wad_to_decimal(market.get("lltv"))
    if market_state.get("netBorrowApy") is not None:
        enriched["borrow_apy"] = safe_float(market_state.get("netBorrowApy"))
    elif market_state.get("borrowApy") is not None:
        enriched["borrow_apy"] = safe_float(market_state.get("borrowApy"))
    if position.get("healthFactor") is not None:
        enriched["live_health_factor"] = safe_float(position.get("healthFactor"))
    if position.get("priceVariationToLiquidationPrice") is not None:
        enriched["live_liquidation_price_variation"] = safe_float(
            position.get("priceVariationToLiquidationPrice")
        )
    enriched["live_value_source"] = "morpho"


def apply_aave_live_values(enriched: dict[str, Any], aave: dict[str, Any], base_decimals: int) -> None:
    divisor = 10 ** int(base_decimals or 8)
    collateral = safe_float(aave.get("totalCollateralBase")) / divisor
    debt = safe_float(aave.get("totalDebtBase")) / divisor
    if collateral:
        enriched["collateral_usd"] = collateral
    if debt:
        enriched["debt_usd"] = debt
    if collateral or debt:
        enriched["equity_usd"] = max(collateral - debt, 0.0)
    if aave.get("currentLiquidationThresholdBps") is not None:
        enriched["liquidation_threshold"] = safe_float(aave.get("currentLiquidationThresholdBps")) / 10_000.0
    if aave.get("ltvBps") is not None:
        enriched["target_ltv"] = safe_float(aave.get("ltvBps")) / 10_000.0
    if aave.get("healthFactor") is not None:
        enriched["live_health_factor"] = safe_float(aave.get("healthFactor"))
    enriched["live_value_source"] = "aave-v3"


def loop_exposure(equity_usd: float, target_ltv: float, iterations: int) -> tuple[float, float]:
    if iterations <= 0 or target_ltv <= 0:
        return equity_usd, 0.0
    collateral = equity_usd * sum(target_ltv**i for i in range(iterations + 1))
    debt = equity_usd * sum(target_ltv**i for i in range(1, iterations + 1))
    return collateral, debt


def simulate_loop(loop: dict[str, Any]) -> dict[str, Any]:
    equity = safe_float(loop.get("equity_usd"))
    collateral = safe_float(loop.get("collateral_usd"))
    debt = safe_float(loop.get("debt_usd"))
    target_ltv = safe_float(loop.get("target_ltv"))
    iterations = int(safe_float(loop.get("loop_iterations"), 0))

    if equity <= 0 and collateral > debt:
        equity = collateral - debt
    if collateral <= 0 and equity > 0:
        collateral, debt = loop_exposure(equity, target_ltv, iterations)
    if equity <= 0:
        equity = max(collateral - debt, 0.0)

    pt_apy = safe_float(loop.get("pt_apy"))
    yt_apy = safe_float(loop.get("yt_apy"))
    gross_yield_apy = pt_apy or yt_apy or safe_float(loop.get("yield_apy"))
    borrow_apy = safe_float(loop.get("borrow_apy"))
    liquidation_threshold = safe_float(loop.get("liquidation_threshold"))
    slippage_bps = safe_float(loop.get("slippage_bps"))
    gas_usd = safe_float(loop.get("gas_usd"))
    traded_notional = max(collateral, debt)
    one_time_cost = traded_notional * (slippage_bps / 10_000.0) + gas_usd
    annual_gross = collateral * gross_yield_apy
    annual_borrow = debt * borrow_apy
    annual_net = annual_gross - annual_borrow
    net_after_cost = annual_net - one_time_cost
    ltv = debt / collateral if collateral else 0.0
    health_factor = (collateral * liquidation_threshold / debt) if debt and liquidation_threshold else None
    liquidation_drop = None
    if debt and collateral and liquidation_threshold:
        liquidation_price_multiplier = debt / (collateral * liquidation_threshold)
        liquidation_drop = max(0.0, 1.0 - liquidation_price_multiplier)

    return {
        "equityUsd": round(equity, 4),
        "collateralUsd": round(collateral, 4),
        "debtUsd": round(debt, 4),
        "ltv": round(ltv, 6),
        "targetLtv": target_ltv,
        "liquidationThreshold": liquidation_threshold,
        "healthFactor": round(health_factor, 6) if health_factor is not None else None,
        "liquidationCollateralDropPct": round(liquidation_drop * 100, 4) if liquidation_drop is not None else None,
        "grossYieldApy": gross_yield_apy,
        "borrowApy": borrow_apy,
        "annualGrossYieldUsd": round(annual_gross, 4),
        "annualBorrowCostUsd": round(annual_borrow, 4),
        "estimatedOneTimeCostUsd": round(one_time_cost, 4),
        "netApyBeforeOneTimeCost": round(annual_net / equity, 6) if equity else None,
        "netApyAfterOneTimeCost": round(net_after_cost / equity, 6) if equity else None,
    }


def load_pendle_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    args = argparse.Namespace(
        no_pendle=False,
        self_test=False,
        pendle_input_json=None,
        pendle_page_size=100,
        pendle_max_markets=600,
        pendle_url=yield_monitor.PENDLE_MARKETS_URL,
        min_tvl_usd=0,
        high_apy_warning=50,
        risk_profile="balanced",
    )
    try:
        markets = yield_monitor.load_pendle_markets(args)
    except Exception:
        return {}
    by_symbol: dict[str, dict[str, Any]] = {}
    for opp in yield_monitor.pendle_opportunities(markets, args):
        scored = yield_monitor.score_pool(opp, args)
        by_symbol[scored["symbol"].lower()] = scored
        if scored.get("pool"):
            by_symbol[scored["pool"].lower()] = scored
    return by_symbol


def days_to_expiry(expiry: str | None) -> float | None:
    if not expiry:
        return None
    try:
        date = dt.datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    except ValueError:
        try:
            date = dt.datetime.fromisoformat(expiry + "T00:00:00+00:00")
        except ValueError:
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=dt.timezone.utc)
    return (date - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86_400


def classify(snapshot: dict[str, Any], config: dict[str, Any]) -> tuple[str, list[str]]:
    risk = config.get("risk", {})
    messages: list[str] = []
    severity = "ok"
    hf = snapshot.get("healthFactor")
    if hf is not None:
        if hf <= safe_float(risk.get("critical_health_factor"), 1.1):
            severity = "critical"
            messages.append(f"health factor critical: {hf:.3f}")
        elif hf <= safe_float(risk.get("min_health_factor"), 1.3):
            severity = "warning"
            messages.append(f"health factor below target: {hf:.3f}")

    if snapshot.get("ltv", 0) > safe_float(risk.get("max_ltv"), 0.7):
        severity = max_severity(severity, "warning")
        messages.append(f"LTV above configured max: {snapshot['ltv']:.2%}")
    if snapshot.get("borrowApy", 0) > safe_float(risk.get("max_borrow_apy"), 0.12):
        severity = max_severity(severity, "warning")
        messages.append(f"borrow APY above configured max: {snapshot['borrowApy']:.2%}")
    net_apy = snapshot.get("netApyAfterOneTimeCost")
    if net_apy is not None and net_apy < 0:
        severity = max_severity(severity, "warning")
        messages.append(f"net APY after estimated costs is negative: {snapshot['netApyAfterOneTimeCost']:.2%}")
    dte = snapshot.get("daysToMaturity")
    if dte is not None and dte <= safe_float(risk.get("days_to_maturity_warning"), 10):
        severity = max_severity(severity, "warning")
        messages.append(f"maturity is close: {dte:.1f} days")
    return severity, messages


def max_severity(left: str, right: str) -> str:
    order = {"ok": 0, "info": 1, "warning": 2, "critical": 3}
    return left if order.get(left, 0) >= order.get(right, 0) else right


def action_plan(loop: dict[str, Any], snapshot: dict[str, Any], severity: str, reasons: list[str]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    if severity in {"warning", "critical"}:
        debt = safe_float(snapshot.get("debtUsd"))
        collateral = safe_float(snapshot.get("collateralUsd"))
        target_ltv = safe_float(loop.get("target_ltv"))
        if debt and collateral and target_ltv:
            target_debt = collateral * target_ltv
            repay_usd = max(0.0, debt - target_debt)
            add_collateral_usd = max(0.0, debt / target_ltv - collateral)
            actions.append(
                {
                    "type": "repay-debt",
                    "estimatedUsd": round(repay_usd, 4),
                    "status": "draft-only",
                    "reason": "reduce LTV toward target",
                }
            )
            actions.append(
                {
                    "type": "add-collateral",
                    "estimatedUsd": round(add_collateral_usd, 4),
                    "status": "draft-only",
                    "reason": "increase collateral buffer",
                }
            )
        actions.append(
            {
                "type": "close-or-deleverage-loop",
                "status": "draft-only",
                "reason": "manual review required before any transaction",
            }
        )
    return {
        "name": loop.get("name"),
        "protocol": loop.get("protocol"),
        "chain": loop.get("chain"),
        "severity": severity,
        "reasons": reasons,
        "actions": actions,
        "requiresManualWalletApproval": True,
        "unattendedSigning": False,
    }


def enrich_loop(loop: dict[str, Any], config: dict[str, Any], pendle_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    enriched = dict(loop)
    symbol = str(loop.get("pendle_symbol") or "").lower()
    pool = str(loop.get("pendle_market") or "").lower()
    pendle = pendle_map.get(symbol) or pendle_map.get(pool)
    if pendle:
        apy_decimal = safe_float(pendle.get("apy")) / 100.0
        if str(pendle.get("positionType")) == "yt":
            enriched["yt_apy"] = apy_decimal
        else:
            enriched["pt_apy"] = apy_decimal
        enriched["pendle_current"] = pendle
        enriched["expiry"] = pendle.get("expiry")

    protocol = str(loop.get("protocol") or "").lower()
    chain_key = str(loop.get("chain") or "")
    chain = (config.get("chains") or {}).get(chain_key, {})
    chain_id = evm_chain_id(chain)
    wallet = config.get("wallet")
    live_first = str(loop.get("value_source") or "live-first").lower() != "manual"
    morpho_key = str(loop.get("morpho_market_unique_key") or loop.get("morpho_market_id") or "")
    if protocol == "morpho" and morpho_key and chain_id:
        try:
            market = fetch_morpho_market(
                morpho_key,
                chain_id,
                str(config.get("morpho_graphql_url") or MORPHO_GRAPHQL_URL),
            )
            state = market.get("state") or {}
            if state.get("netBorrowApy") is not None:
                enriched["borrow_apy"] = safe_float(state.get("netBorrowApy"))
            elif state.get("borrowApy") is not None:
                enriched["borrow_apy"] = safe_float(state.get("borrowApy"))
            if market.get("lltv") is not None:
                enriched["liquidation_threshold"] = wad_to_decimal(market.get("lltv"))
            enriched["live_value_source"] = "morpho-market+manual-position"
            enriched["morpho_market"] = market
        except Exception as exc:
            enriched["morpho_error"] = str(exc)
        if wallet and live_first:
            try:
                position = fetch_morpho_position(
                    str(wallet),
                    morpho_key,
                    chain_id,
                    str(config.get("morpho_graphql_url") or MORPHO_GRAPHQL_URL),
                )
                enriched["morpho_position"] = position
                if position:
                    apply_morpho_live_values(enriched, position)
            except Exception as exc:
                enriched["morpho_position_error"] = str(exc)
            try:
                user = fetch_morpho_user(
                    str(wallet),
                    chain_id,
                    str(config.get("morpho_graphql_url") or MORPHO_GRAPHQL_URL),
                )
                enriched["morpho_user"] = user
            except Exception as exc:
                enriched["morpho_user_error"] = str(exc)

    if protocol == "aave-v3" and wallet and chain.get("aave_pool") and live_first:
        rpc = os.environ.get(str(chain.get("rpc_url_env"))) if chain.get("rpc_url_env") else None
        rpc = rpc or env_value(chain.get("rpc_url"))
        if rpc:
            try:
                aave = aave_user_account_data(rpc, str(chain["aave_pool"]), str(wallet))
                enriched["aave_account"] = aave
                apply_aave_live_values(enriched, aave, int(chain.get("aave_base_decimals") or 8))
            except Exception as exc:
                enriched["aave_error"] = str(exc)
    return enriched


def evaluate_loop(loop: dict[str, Any], config: dict[str, Any], pendle_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    enriched = enrich_loop(loop, config, pendle_map)
    simulated = simulate_loop(enriched)
    aave = enriched.get("aave_account") or {}
    if enriched.get("live_health_factor") is not None:
        simulated["healthFactor"] = enriched["live_health_factor"]
    if enriched.get("live_liquidation_price_variation") is not None:
        simulated["liquidationCollateralDropPct"] = round(
            safe_float(enriched.get("live_liquidation_price_variation")) * 100, 4
        )
    if aave:
        simulated["aaveAccountData"] = aave
    if enriched.get("morpho_position"):
        simulated["morphoPosition"] = enriched["morpho_position"]
    if enriched.get("morpho_market"):
        simulated["morphoMarket"] = enriched["morpho_market"]
    expiry = enriched.get("expiry")
    simulated["daysToMaturity"] = days_to_expiry(expiry)
    simulated["name"] = enriched.get("name")
    simulated["protocol"] = enriched.get("protocol")
    simulated["chain"] = enriched.get("chain")
    simulated["pendleSymbol"] = enriched.get("pendle_symbol")
    simulated["liveValueSource"] = enriched.get("live_value_source", "manual-or-config")
    simulated["errors"] = {
        key: value for key, value in enriched.items() if key.endswith("_error") and value
    }
    severity, reasons = classify(simulated, config)
    simulated["severity"] = severity
    simulated["reasons"] = reasons
    simulated["actionPlan"] = action_plan(enriched, simulated, severity, reasons)
    return simulated


def alert_text(report: dict[str, Any]) -> str:
    lines = [f"Defimax Loop Monitor | {report['generatedAt']}"]
    for item in report["positions"]:
        net = item.get("netApyAfterOneTimeCost")
        net_text = "n/a" if net is None else f"{net:.2%}"
        lines.append(
            "{severity}: {name} | HF={hf} | LTV={ltv:.2%} | net={net} | debt={debt}".format(
                severity=item["severity"].upper(),
                name=item["name"],
                hf="n/a" if item.get("healthFactor") is None else f"{item['healthFactor']:.3f}",
                ltv=item.get("ltv", 0.0),
                net=net_text,
                debt=money(item.get("debtUsd", 0.0)),
            )
        )
        lines.append(f"- source: {item.get('liveValueSource', 'manual-or-config')}")
        for reason in item.get("reasons") or []:
            lines.append(f"- {reason}")
    return "\n".join(lines)


def send_telegram(config: dict[str, Any], text: str) -> bool:
    tg = ((config.get("alerts") or {}).get("telegram") or {})
    if not tg.get("enabled"):
        return False
    token = env_value(tg.get("bot_token_env") or tg.get("bot_token"))
    chat_id = env_value(tg.get("chat_id_env") or tg.get("chat_id"))
    if not token or not chat_id:
        raise RuntimeError("Telegram enabled but token/chat id is missing")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return 200 <= resp.status < 300


def send_discord(config: dict[str, Any], text: str) -> bool:
    discord = ((config.get("alerts") or {}).get("discord") or {})
    if not discord.get("enabled"):
        return False
    webhook = env_value(discord.get("webhook_url_env") or discord.get("webhook_url"))
    if not webhook:
        raise RuntimeError("Discord enabled but webhook URL is missing")
    payload = json.dumps({"content": text[:1900]}).encode("utf-8")
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return 200 <= resp.status < 300


def store_report(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    for item in report["positions"]:
        conn.execute(
            """
            INSERT INTO position_snapshots
              (ts, name, protocol, chain, severity, health_factor, ltv, net_apy, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report["generatedAt"],
                item.get("name"),
                item.get("protocol"),
                item.get("chain"),
                item.get("severity"),
                item.get("healthFactor"),
                item.get("ltv"),
                item.get("netApyAfterOneTimeCost"),
                json.dumps(item, sort_keys=True),
            ),
        )
        if item.get("severity") in {"warning", "critical"}:
            conn.execute(
                "INSERT INTO alerts (ts, name, severity, message, delivered) VALUES (?, ?, ?, ?, 0)",
                (report["generatedAt"], item.get("name"), item["severity"], "; ".join(item.get("reasons") or [])),
            )
    conn.commit()


def has_recent_alert(conn: sqlite3.Connection, name: str, severity: str, min_interval_hours: float) -> bool:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=min_interval_hours)
    rows = conn.execute(
        """
        SELECT ts FROM alerts
        WHERE name = ? AND severity = ? AND delivered = 1
        ORDER BY ts DESC LIMIT 1
        """,
        (name, severity),
    ).fetchall()
    for (raw_ts,) in rows:
        try:
            ts = dt.datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        if ts >= cutoff:
            return True
    return False


def mark_alerts_delivered(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    for item in report["positions"]:
        if item.get("severity") in {"warning", "critical"}:
            conn.execute(
                """
                UPDATE alerts SET delivered = 1
                WHERE name = ? AND severity = ? AND delivered = 0
                """,
                (item.get("name"), item.get("severity")),
            )
    conn.commit()


def positions_to_alert(conn: sqlite3.Connection, report: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    min_interval = safe_float(((config.get("alerts") or {}).get("min_interval_hours")), 6)
    selected = []
    for item in report["positions"]:
        if item.get("severity") not in {"warning", "critical"}:
            continue
        if has_recent_alert(conn, str(item.get("name")), str(item.get("severity")), min_interval):
            continue
        selected.append(item)
    return selected


def run_monitor(args: argparse.Namespace) -> int:
    config = load_json(expand_path(args.config))
    conn = init_db(config.get("database") or DEFAULT_DB)
    pendle_map = load_pendle_map(config)
    positions = [
        evaluate_loop(loop, config, pendle_map)
        for loop in config.get("loops", [])
        if loop.get("enabled", True)
    ]
    report = {
        "generatedAt": utc_now(),
        "wallet": config.get("wallet"),
        "mode": config.get("mode", "monitor-only"),
        "positions": positions,
    }
    store_report(conn, report)
    alert_positions = positions_to_alert(conn, report, config)
    alert_report = {**report, "positions": alert_positions}
    text = alert_text(report if not alert_positions else alert_report)
    if args.send_alerts and alert_positions:
        delivered = []
        try:
            delivered.append(("telegram", send_telegram(config, alert_text(alert_report))))
        except Exception as exc:
            delivered.append(("telegram_error", str(exc)))
        try:
            delivered.append(("discord", send_discord(config, alert_text(alert_report))))
        except Exception as exc:
            delivered.append(("discord_error", str(exc)))
        report["alertDelivery"] = delivered
        if any(value is True for _, value in delivered):
            mark_alerts_delivered(conn, alert_report)
    report["alertCandidates"] = len(alert_positions)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(text)
    return 0


def run_simulate(args: argparse.Namespace) -> int:
    loop = {
        "equity_usd": args.capital_usd,
        "target_ltv": args.target_ltv,
        "loop_iterations": args.iterations,
        "liquidation_threshold": args.liquidation_threshold,
        "pt_apy": args.pt_apy,
        "borrow_apy": args.borrow_apy,
        "slippage_bps": args.slippage_bps,
        "gas_usd": args.gas_usd,
    }
    print(json.dumps(simulate_loop(loop), indent=2, sort_keys=True))
    return 0


def run_install_cron(args: argparse.Namespace) -> int:
    config_path = expand_path(args.config)
    script = Path(__file__).resolve()
    if args.schedule == "daily":
        expr = "0 12 * * *"
    elif args.schedule == "6h":
        expr = "0 */6 * * *"
    else:
        expr = args.schedule
    line = f"{expr} python3 {script} monitor --config {config_path} --send-alerts --json >> ~/.cache/defimax/cron.log 2>&1"
    print(line)
    if args.write_cron_file:
        target = Path(args.write_cron_file).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(f"Cron line written to {target}")
    return 0


def run_tx_plan(args: argparse.Namespace) -> int:
    config = load_json(expand_path(args.config))
    pendle_map = load_pendle_map(config)
    selected = None
    for loop in config.get("loops", []):
        if loop.get("name") == args.loop:
            selected = evaluate_loop(loop, config, pendle_map)
            break
    if not selected:
        raise SystemExit(f"loop not found: {args.loop}")
    plan = selected["actionPlan"]
    plan["requestedAction"] = args.action
    plan["status"] = "requires-explicit-wallet-confirmation"
    plan["note"] = (
        "This skill does not store private keys or sign unattended transactions. "
        "Use walletconnect-mqc and confirm the exact transaction in the wallet."
    )
    if args.output:
        write_json(args.output, plan)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def run_execute(args: argparse.Namespace) -> int:
    plan = load_json(args.plan)
    if not args.confirm:
        print("Refusing execution: pass --confirm after reviewing the plan.")
        return 2
    if plan.get("unattendedSigning") is not False:
        print("Refusing execution: plan must explicitly disable unattended signing.")
        return 2
    print("Execution is intentionally delegated to walletconnect-mqc with wallet-side approval.")
    print("Review the plan, connect the wallet, and approve only if the on-wallet transaction matches the plan.")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def discover_morpho_positions(address: str, config: dict[str, Any], chain_keys: set[str] | None = None) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    endpoint = str(config.get("morpho_graphql_url") or MORPHO_GRAPHQL_URL)
    for key, chain in (config.get("chains") or {}).items():
        if chain_keys and str(key).lower() not in chain_keys:
            continue
        chain_id = evm_chain_id(chain)
        if not chain_id:
            continue
        try:
            user = fetch_morpho_user(address, chain_id, endpoint)
        except Exception as exc:
            positions.append({"source": "morpho", "chain": key, "error": str(exc)})
            continue
        for item in user.get("marketPositions") or []:
            state = item.get("state") or {}
            collateral_usd = safe_float(state.get("collateralUsd"))
            debt_usd = safe_float(state.get("borrowAssetsUsd"))
            if collateral_usd <= 0 and debt_usd <= 0:
                continue
            market = item.get("market") or {}
            market_id = str(market.get("marketId") or "")
            lltv = wad_to_decimal(market.get("lltv"))
            positions.append(
                {
                    "source": "morpho",
                    "chain": key,
                    "chainId": chain_id,
                    "marketId": market_id,
                    "collateralUsd": collateral_usd,
                    "debtUsd": debt_usd,
                    "marginUsd": safe_float(state.get("marginUsd")),
                    "healthFactor": item.get("healthFactor"),
                    "priceVariationToLiquidationPrice": item.get("priceVariationToLiquidationPrice"),
                    "liquidationThreshold": lltv,
                    "suggestedLoop": {
                        "name": f"Morpho {market_id[:10]} on {key}",
                        "enabled": True,
                        "protocol": "morpho",
                        "chain": key,
                        "position_type": "discovered-loop",
                        "morpho_market_unique_key": market_id,
                        "morpho_market_id": market_id,
                        "value_source": "live-first",
                        "collateral_usd": collateral_usd,
                        "debt_usd": debt_usd,
                        "equity_usd": max(collateral_usd - debt_usd, 0.0),
                        "target_ltv": debt_usd / collateral_usd if collateral_usd else 0.0,
                        "liquidation_threshold": lltv,
                        "borrow_apy": 0.0,
                        "pt_apy": 0.0,
                        "slippage_bps": 30,
                        "gas_usd": 25,
                    },
                }
            )
    return positions


def discover_aave_positions(address: str, config: dict[str, Any], chain_keys: set[str] | None = None) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    for key, chain in (config.get("chains") or {}).items():
        if chain_keys and str(key).lower() not in chain_keys:
            continue
        pool = chain.get("aave_pool")
        if not pool:
            continue
        chain_id = evm_chain_id(chain)
        if not chain_id:
            continue
        rpc = rpc_url_for_chain(config, chain_id)
        if not rpc:
            positions.append({"source": "aave-v3", "chain": key, "error": "missing RPC URL"})
            continue
        try:
            data = aave_user_account_data(rpc, str(pool), address)
        except Exception as exc:
            positions.append({"source": "aave-v3", "chain": key, "error": str(exc)})
            continue
        decimals = int(chain.get("aave_base_decimals") or 8)
        divisor = 10**decimals
        collateral_usd = safe_float(data.get("totalCollateralBase")) / divisor
        debt_usd = safe_float(data.get("totalDebtBase")) / divisor
        if collateral_usd <= 0 and debt_usd <= 0:
            continue
        positions.append(
            {
                "source": "aave-v3",
                "chain": key,
                "chainId": chain_id,
                "pool": pool,
                "collateralUsd": collateral_usd,
                "debtUsd": debt_usd,
                "healthFactor": data.get("healthFactor"),
                "ltv": safe_float(data.get("ltvBps")) / 10_000.0,
                "liquidationThreshold": safe_float(data.get("currentLiquidationThresholdBps")) / 10_000.0,
                "suggestedLoop": {
                    "name": f"Aave V3 aggregate on {key}",
                    "enabled": True,
                    "protocol": "aave-v3",
                    "chain": key,
                    "position_type": "health-monitor",
                    "value_source": "live-first",
                    "collateral_usd": collateral_usd,
                    "debt_usd": debt_usd,
                    "equity_usd": max(collateral_usd - debt_usd, 0.0),
                    "target_ltv": safe_float(data.get("ltvBps")) / 10_000.0,
                    "liquidation_threshold": safe_float(data.get("currentLiquidationThresholdBps")) / 10_000.0,
                    "borrow_apy": 0.0,
                    "pt_apy": 0.0,
                    "slippage_bps": 30,
                    "gas_usd": 25,
                },
            }
        )
    return positions


def discover_pendle_balances(
    address: str, config: dict[str, Any], chain_keys: set[str] | None = None, max_markets: int = 300
) -> list[dict[str, Any]]:
    args = argparse.Namespace(
        no_pendle=False,
        self_test=False,
        pendle_input_json=None,
        pendle_page_size=100,
        pendle_max_markets=max_markets,
        pendle_url=yield_monitor.PENDLE_MARKETS_URL,
        min_tvl_usd=0,
        high_apy_warning=50,
        risk_profile="balanced",
    )
    try:
        markets = yield_monitor.load_pendle_markets(args)
    except Exception as exc:
        return [{"source": "pendle-core", "error": str(exc)}]

    allowed_chain_ids = set()
    for key, chain in (config.get("chains") or {}).items():
        if chain_keys and str(key).lower() not in chain_keys:
            continue
        chain_id = evm_chain_id(chain)
        if chain_id:
            allowed_chain_ids.add(chain_id)

    found: list[dict[str, Any]] = []
    for market in markets:
        if not yield_monitor.is_active_expiry(market.get("expiry")):
            continue
        chain_id = int(safe_float(market.get("chainId")))
        if allowed_chain_ids and chain_id not in allowed_chain_ids:
            continue
        rpc = rpc_url_for_chain(config, chain_id)
        if not rpc:
            continue
        name = str(market.get("name") or "unknown")
        token_specs = [
            ("pt", market.get("pt"), f"PT-{name}"),
            ("yt", market.get("yt"), f"YT-{name}"),
            ("lp", f"{chain_id}-{market.get('address')}", f"LP-{name}"),
        ]
        for position_type, token_id, symbol in token_specs:
            parsed = parse_token_id(str(token_id) if token_id else "")
            if not parsed:
                continue
            _, token_address = parsed
            try:
                raw_balance = erc20_balance_of(rpc, token_address, address)
            except Exception:
                continue
            if raw_balance <= 0:
                continue
            decimals = erc20_decimals(rpc, token_address)
            amount = raw_balance / (10 ** decimals) if decimals is not None else None
            found.append(
                {
                    "source": "pendle-core",
                    "chain": yield_monitor.chain_name(chain_id),
                    "chainId": chain_id,
                    "positionType": position_type,
                    "symbol": symbol,
                    "token": token_address,
                    "market": market.get("address"),
                    "expiry": yield_monitor.short_expiry(market.get("expiry")),
                    "rawBalance": str(raw_balance),
                    "decimals": decimals,
                    "amount": amount,
                    "apy": yield_monitor.decimal_to_percent((market.get("details") or {}).get("impliedApy"))
                    if position_type == "pt"
                    else yield_monitor.decimal_to_percent((market.get("details") or {}).get("ytFloatingApy"))
                    if position_type == "yt"
                    else yield_monitor.decimal_to_percent((market.get("details") or {}).get("aggregatedApy")),
                    "suggestedLoop": {
                        "name": f"Pendle {symbol} balance on {yield_monitor.chain_name(chain_id)}",
                        "enabled": True,
                        "protocol": "pendle",
                        "chain": yield_monitor.chain_name(chain_id).lower().replace(" ", "-"),
                        "position_type": position_type,
                        "pendle_symbol": symbol,
                        "pendle_market": str(market.get("address") or ""),
                        "value_source": "wallet-balance",
                        "collateral_usd": 0,
                        "debt_usd": 0,
                        "equity_usd": 0,
                        "target_ltv": 0,
                        "liquidation_threshold": 0,
                        "borrow_apy": 0,
                        "pt_apy": yield_monitor.decimal_to_percent((market.get("details") or {}).get("impliedApy")) / 100.0,
                    },
                }
            )
    return found


def merge_discovered_config(config: dict[str, Any], address: str, discovery: dict[str, Any], include_pendle: bool) -> dict[str, Any]:
    updated = dict(config)
    updated["wallet"] = address
    loops = []
    seen = set()
    for section in ("morpho", "aave"):
        for item in discovery.get(section, []):
            loop = item.get("suggestedLoop")
            if not loop:
                continue
            key = (loop.get("protocol"), loop.get("chain"), loop.get("morpho_market_id"), loop.get("name"))
            if key in seen:
                continue
            seen.add(key)
            loops.append(loop)
    if include_pendle:
        for item in discovery.get("pendleBalances", []):
            loop = item.get("suggestedLoop")
            if loop:
                loops.append(loop)
    updated["loops"] = loops
    return updated


def solana_defi_adapter_status(config: dict[str, Any]) -> dict[str, Any]:
    enabled = (config.get("solana_defi") or {}).get("enabled_protocols") or list(SOLANA_DEFI_ADAPTER_TARGETS)
    protocols = {
        name: SOLANA_DEFI_ADAPTER_TARGETS.get(name, {"status": "adapter-required"})
        for name in enabled
    }
    return {
        "source": "solana-defi",
        "status": "rpc-ready-adapter-required",
        "rpc": solana_rpc_url(config),
        "protocols": protocols,
        "note": "Solana wallet accepted, but live position discovery needs protocol-specific account parsers or SDK adapters.",
    }


def run_discover_wallet(args: argparse.Namespace) -> int:
    is_evm_wallet = is_valid_address(args.address)
    is_solana_wallet = is_valid_solana_address(args.address)
    if not is_evm_wallet and not is_solana_wallet:
        raise SystemExit(f"invalid EVM or Solana address: {args.address}")
    config = example_config()
    config_path = expand_path(args.config) if args.config else None
    if config_path and config_path.exists():
        config = load_json(config_path)
    config["wallet"] = args.address
    chain_keys = {item.strip().lower() for item in args.chains.split(",") if item.strip()} if args.chains else None
    wants_solana = is_solana_wallet or chain_keys is None or "solana" in chain_keys
    discovery = {
        "generatedAt": utc_now(),
        "wallet": args.address,
        "walletType": "evm" if is_evm_wallet else "solana",
        "morpho": discover_morpho_positions(args.address, config, chain_keys) if is_evm_wallet else [],
        "aave": discover_aave_positions(args.address, config, chain_keys) if is_evm_wallet else [],
        "pendleBalances": [],
    }
    if wants_solana:
        discovery["solana"] = solana_defi_adapter_status(config)
    if is_evm_wallet and not args.no_pendle:
        discovery["pendleBalances"] = discover_pendle_balances(
            args.address, config, chain_keys, max_markets=args.max_pendle_markets
        )
    discovery["summary"] = {
        "morphoPositions": len([x for x in discovery["morpho"] if not x.get("error")]),
        "aavePositions": len([x for x in discovery["aave"] if not x.get("error")]),
        "pendleBalances": len([x for x in discovery["pendleBalances"] if not x.get("error")]),
        "solanaProtocolAdapters": len((discovery.get("solana") or {}).get("protocols") or {}),
    }
    if args.write_config:
        output_config = expand_path(args.write_config)
        merged = merge_discovered_config(config, args.address, discovery, args.include_pendle_in_config)
        write_json(output_config, merged)
        discovery["writtenConfig"] = str(output_config)
    print(json.dumps(discovery, indent=2, sort_keys=True))
    return 0


def run_check_rpcs(args: argparse.Namespace) -> int:
    config = example_config()
    config_path = expand_path(args.config) if args.config else None
    if config_path and config_path.exists():
        config = load_json(config_path)
    chain_keys = {item.strip().lower() for item in args.chains.split(",") if item.strip()} if args.chains else None
    rows = []
    for key, chain in (config.get("chains") or {}).items():
        if chain_keys and str(key).lower() not in chain_keys:
            continue
        if str(chain.get("family") or "").lower() == "solana":
            rpc = solana_rpc_url(config)
            rows.append(
                {
                    "chain": key,
                    "chainId": chain.get("chain_id"),
                    "family": "solana",
                    "rpc": rpc,
                    "ok": bool(rpc and solana_rpc_works(rpc)),
                }
            )
            continue
        chain_id = evm_chain_id(chain)
        if not chain_id:
            rows.append(
                {
                    "chain": key,
                    "chainId": chain.get("chain_id"),
                    "family": str(chain.get("family") or "unknown"),
                    "rpc": None,
                    "ok": False,
                    "error": "unsupported non-EVM chain config",
                }
            )
            continue
        rpc = rpc_url_for_chain(config, chain_id)
        rows.append(
            {
                "chain": key,
                "chainId": chain_id,
                "family": "evm",
                "rpc": rpc,
                "ok": bool(rpc and rpc_works_for_chain(rpc, chain_id)),
            }
        )
    print(json.dumps({"checkedAt": utc_now(), "rpcs": rows}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor PT/YT lending loops and guarded action plans.")
    sub = parser.add_subparsers(dest="command", required=True)

    wizard = sub.add_parser("wizard", help="Create a config interactively or write an example config.")
    wizard.add_argument("--config", default=DEFAULT_CONFIG)
    wizard.add_argument("--write-example", action="store_true")
    wizard.set_defaults(func=run_wizard)

    monitor = sub.add_parser("monitor", help="Evaluate configured loops and store history.")
    monitor.add_argument("--config", default=DEFAULT_CONFIG)
    monitor.add_argument("--json", action="store_true")
    monitor.add_argument("--send-alerts", action="store_true")
    monitor.set_defaults(func=run_monitor)

    discover = sub.add_parser("discover-wallet", help="Discover DeFi positions from a wallet address.")
    discover.add_argument("--address", required=True)
    discover.add_argument("--config", default=DEFAULT_CONFIG)
    discover.add_argument("--chains", help="Comma-separated config chain keys, e.g. ethereum,base.")
    discover.add_argument("--no-pendle", action="store_true")
    discover.add_argument("--max-pendle-markets", type=int, default=300)
    discover.add_argument("--write-config", help="Write a config with discovered monitor loops.")
    discover.add_argument("--include-pendle-in-config", action="store_true")
    discover.set_defaults(func=run_discover_wallet)

    check_rpcs = sub.add_parser("check-rpcs", help="Check configured and integrated public RPC fallbacks.")
    check_rpcs.add_argument("--config", default=DEFAULT_CONFIG)
    check_rpcs.add_argument("--chains", help="Comma-separated config chain keys.")
    check_rpcs.set_defaults(func=run_check_rpcs)

    sim = sub.add_parser("simulate-loop", help="Simulate recursive PT/YT loop economics.")
    sim.add_argument("--capital-usd", type=float, required=True)
    sim.add_argument("--target-ltv", type=float, required=True)
    sim.add_argument("--iterations", type=int, default=3)
    sim.add_argument("--liquidation-threshold", type=float, required=True)
    sim.add_argument("--pt-apy", type=float, required=True, help="Decimal APY, e.g. 0.18")
    sim.add_argument("--borrow-apy", type=float, required=True, help="Decimal APY, e.g. 0.07")
    sim.add_argument("--slippage-bps", type=float, default=30)
    sim.add_argument("--gas-usd", type=float, default=25)
    sim.set_defaults(func=run_simulate)

    cron = sub.add_parser("install-cron", help="Print or write a cron line. Does not install automatically.")
    cron.add_argument("--config", default=DEFAULT_CONFIG)
    cron.add_argument("--schedule", default="6h")
    cron.add_argument("--write-cron-file")
    cron.set_defaults(func=run_install_cron)

    tx_plan = sub.add_parser("tx-plan", help="Create a guarded action plan for a configured loop.")
    tx_plan.add_argument("--config", default=DEFAULT_CONFIG)
    tx_plan.add_argument("--loop", required=True)
    tx_plan.add_argument("--action", choices=["repay", "add-collateral", "deleverage", "close"], required=True)
    tx_plan.add_argument("--output")
    tx_plan.set_defaults(func=run_tx_plan)

    execute = sub.add_parser("execute-plan", help="Display wallet-confirmation instructions for a tx plan.")
    execute.add_argument("--plan", required=True)
    execute.add_argument("--confirm", action="store_true")
    execute.set_defaults(func=run_execute)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
