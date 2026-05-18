## v0.1.2 — 2026-05-18

> Bump: PATCH
> Compatibilidade: adiciona fonte de mercados Solana PT/YT sem alterar comandos existentes

### Added
- `yield_monitor.py` agora aceita mercados Solana `PT`/`YT` via `--solana-yield-input-json`, `--solana-yield-url` ou `DEFIMAX_SOLANA_YIELD_MARKETS_URL`.
- Normalização de mercados Exponent/RateX-style para `PT`, `YT` e `LP`, com chain `Solana`, maturidade, TVL, liquidez e flags de risco.
- Fixtures de self-test com exemplos Solana PT/YT para validar ranking e entrega Telegram.

### Changed
- Entrega Telegram agora mostra seções genéricas `PT / yield fixo`, `YT / Yield Tokens` e `LP de yield`, cobrindo Pendle e Solana.
- Flag de baixa liquidez passou a ser `low-market-liquidity`, aplicável a Pendle e Solana.

### Notes
- A skill não inventa APY de Exponent/RateX quando app/API não entrega dado confiável; para produção, use API oficial, indexer próprio ou JSON exportado.

### Validation
- [x] `python3 -m py_compile scripts/yield_monitor.py scripts/position_monitor.py scripts/telegram_delivery.py`
- [x] `python3 scripts/yield_monitor.py --self-test --json --position-types pt,yt --chains solana --min-tvl-usd 0 --limit 10`
- [x] `python3 scripts/telegram_delivery.py --dry-run --self-test --position-types pt,yt --chains solana --min-tvl-usd 0 --limit 6`
- [x] Skill Builder quick validation

## v0.1.1 — 2026-05-18

> Bump: PATCH
> Compatibilidade: melhoria de entrega Telegram sem alterar interface principal da skill

### Changed
- Entrega Telegram agora separa oportunidades por Pools DeFi, Pendle PT, Pendle YT e Pendle LP.
- Preview Telegram inclui limite por seção com `--section-limit`.
- Texto de leitura foi ajustado para explicar melhor PT, YT, LP e pools variáveis.

### Validation
- [x] `python3 -m py_compile scripts/yield_monitor.py scripts/position_monitor.py scripts/telegram_delivery.py` passou.
- [x] `python3 scripts/telegram_delivery.py --dry-run --self-test --limit 2` passou.

## v0.1.0 — 2026-05-18

> Bump: MINOR
> Compatibilidade: primeira publicação na org QuickClaw-Skills

### Added
- Publicação inicial da DefiMax na org QuickClaw-Skills.
- Scanner/ranking de oportunidades DeFi via DefiLlama e Pendle Core API.
- Monitor de posições/loops com health factor, risco de liquidação, histórico SQLite e planos de ação guardrailed.
- Preview/entrega de alertas em formato Telegram.

### Security
- A skill opera no limite monitoramento + alerta + plano; não assina transações de forma autônoma.
- Não pede seed phrase, private key, mnemonic ou keystore.

### Migration Notes
- Para alertas reais, tokens/webhooks devem ser configurados via variáveis de ambiente/dashboard, nunca pelo chat.
- RPCs públicos são fallback; para produção, usar RPCs privados via env vars.

### Validation
- [x] SKILL.md frontmatter validado.
- [x] skill.json.version = 0.1.0.
- [x] `python3 scripts/yield_monitor.py --self-test --json --limit 3` passou.
- [x] `python3 scripts/position_monitor.py wizard --write-example` passou.
- [x] `python3 scripts/position_monitor.py monitor --config <example> --json` passou.

### Rollback
- Primeira release na org; rollback = desinstalar a skill ou publicar PATCH corretivo.
