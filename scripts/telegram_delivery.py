#!/usr/bin/env python3
"""Send or preview an emoji-formatted Defimax yield report for Telegram."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from typing import Any

import yield_monitor


TELEGRAM_LIMIT = 4096


def risk_emoji(flags: list[str]) -> str:
    if not flags:
        return "✅"
    if "very-high-apy" in flags or "principal-not-redeemable" in flags:
        return "⚠️"
    if "fixed-maturity" in flags:
        return "🔒"
    if "near-min-tvl" in flags:
        return "🟠"
    return "⚠️"


def type_emoji(position_type: str) -> str:
    mapping = {
        "pt": "🔒",
        "yt": "🔥",
        "lp": "💧",
        "pool": "🏦",
    }
    return mapping.get(str(position_type).lower(), "📊")


def compact_flags(flags: list[str], max_items: int = 3) -> str:
    if not flags:
        return "sem flags críticas"
    shown = flags[:max_items]
    suffix = "" if len(flags) <= max_items else f" +{len(flags) - max_items}"
    return ", ".join(shown) + suffix


def format_telegram_report(opportunities: list[dict[str, Any]], args: Any) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lines = [
        "⚡ Defimax Yield Radar",
        f"🕒 {now}",
        (
            "🎯 Filtros: "
            f"risco={args.risk_profile} | TVL≥{yield_monitor.money(args.min_tvl_usd)} | "
            f"stable={'sim' if args.stable_only else 'não'}"
        ),
        "",
    ]
    if not opportunities:
        lines.append("🟡 Nenhuma oportunidade passou nos filtros agora.")
        return "\n".join(lines)

    lines.append("🔥 Top oportunidades agora")
    for index, item in enumerate(opportunities[: args.limit], start=1):
        flags = item.get("riskFlags") or []
        expiry = f" | vence {item['expiry']}" if item.get("expiry") else ""
        liquidity = item.get("liquidityUsd") or 0
        liquidity_text = f" | liq {yield_monitor.money(liquidity)}" if liquidity else ""
        lines.extend(
            [
                "",
                (
                    f"{index}. {type_emoji(item['positionType'])} {item['project']} "
                    f"{item['symbol']} ({str(item['positionType']).upper()})"
                ),
                (
                    f"   🌐 {item['chain']} | APY {item['apy']:.2f}% | "
                    f"TVL {yield_monitor.money(item['tvlUsd'])}{liquidity_text}{expiry}"
                ),
                f"   {risk_emoji(flags)} Risco: {compact_flags(flags)}",
            ]
        )

    lines.extend(
        [
            "",
            "🧠 Leitura Defimax",
            "🔒 PT = yield fixo até vencimento; conferir liquidez e data.",
            "🔥 YT = exposição ao yield variável; risco maior e principal não é resgatável.",
            "💧 LP = inclui risco de pool, fee, incentivos e profundidade.",
            "",
            "⚠️ Não é recomendação financeira. Antes de agir: app oficial, contrato, slippage, gas, bridge/oracle/depeg e liquidez de saída.",
        ]
    )
    text = "\n".join(lines)
    return text[: TELEGRAM_LIMIT - 20] + "\n…truncado" if len(text) > TELEGRAM_LIMIT else text


def send_telegram(text: str, bot_token_env: str, chat_id_env: str) -> None:
    token = os.environ.get(bot_token_env)
    chat_id = os.environ.get(chat_id_env)
    if not token or not chat_id:
        missing = [name for name, value in ((bot_token_env, token), (chat_id_env, chat_id)) if not value]
        raise RuntimeError(f"missing Telegram env vars: {', '.join(missing)}")
    payload = json.dumps(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API returned not ok: {body}")


def main() -> int:
    parser = yield_monitor.build_arg_parser()
    parser.description = "Send an emoji-formatted Defimax yield report to Telegram."
    parser.set_defaults(stable_only=True, min_tvl_usd=5_000_000, limit=8, risk_profile="balanced")
    parser.add_argument("--dry-run", action="store_true", help="Print the Telegram payload without sending.")
    parser.add_argument("--bot-token-env", default="TELEGRAM_BOT_TOKEN")
    parser.add_argument("--chat-id-env", default="TELEGRAM_CHAT_ID")
    args = parser.parse_args()

    raw = yield_monitor.load_defillama_input(args)
    pendle_markets = yield_monitor.load_pendle_markets(args)
    opportunities = yield_monitor.rank_pools(raw, pendle_markets, args)
    text = format_telegram_report(opportunities, args)

    if args.dry_run:
        print(text)
        return 0

    try:
        send_telegram(text, args.bot_token_env, args.chat_id_env)
    except Exception as exc:
        print(text)
        print(f"\nTelegram delivery failed: {exc}")
        return 2
    print("Telegram delivery sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
