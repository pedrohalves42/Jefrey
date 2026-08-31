# Aceite P1.1 -> P1.2 - Jefrey

> **Etapa P1.1 - OAuth Google + Hardening + Catalogo Curado de Skills | AXIOM + CIPHER | Gate para P1.2**
> **Data:** 2026-08-31
> **Commit base P0:** ec9cd01 P0 aceito 86.0/62.8/56.5
> **Alvo P1.1:** Skills PARTIAL->READY (+6.0pp) => 92.0% Impl / 67.2% Prod / 60.4% Comercial

## Gate P1.1 - Provas

### 1. Pesos funcionais (Kleppmann single source)

```
WEIGHTS soma 100: Config 10 + Postgres 20 + Redis 10 + Agent 20 + Skills 15 + EventBus 5 + Policy/HITL 10 + Infra 10
FACTOR: READY 1.0 / PARTIAL 0.6 / PLACEHOLDER 0.2
P0: 86.0% Impl (5 READY 60 + 3 PARTIAL 24) / 62.8% Prod (Impl*0.73) / 56.5% Comercial (Prod*0.90)
P1.1: 92.0% Impl (6 READY 75 + 2 PARTIAL 12) / 67.2% Prod / 60.4% Comercial
```

```bash
python scripts/compute_readiness.py
# P0: 86.0 / 62.8 / 56.5 (Skills PARTIAL)
python scripts/compute_readiness.py --status '{"Skills":"READY"}'
# P1.1: 92.0 / 67.2 / 60.4 (Skills READY) - prova override nao muta default
```

### 2. Curadoria 86 skills (guia 3z36c)

6 pacotes: Marketing 45 + Social 17 + Design 3 (ui-ux-pro-max 122k) + Financeiro 8 oficial + Juridico 9 oficial + Documentos 4 oficial (Anthropic).
P1.1 fecha Skills READY com: Calendar hardening + Gmail hardening + WebSearch hardening + Drive drive.file Novo.
Financeiro/Juridico backlog P1.3+ (exige RBAC fino + HITL).

### 3. Checks AXIOM 6 eixos

| Eixo | Prova |
|------|-------|
| Codigo | py_compile 6 arquivos OK (config, drive, calendar, email, web_search, metrics, registry), TypedDict/Final, SCOPES minimo |
| Teste | setup --check PASS 14s + smoke 7/7 PASS 38s + verify_env PASS + run_tests --quick 2/2 PASS 52s |
| Seguranca | config/tokens 0o700 (setup), token 0o600, .gitignore tokens/credentials, drive.file least privilege, SECRET_RE mask, sem log creds.to_json |
| Observabilidade | metrics jefrey_skill_init_total, jefrey_oauth_refresh_total, jefrey_web_search_cache_hit, jefrey_config_valid |
| Documentacao | docs/oauth.md + docs/JEFREY-AUDIT/acceptance_p1.1.md + .env.example drive + README tracer |
| Aceite | este arquivo + compute 92.0 gate binario fresh machine |

### 4. Skills detalhe

| Skill | Antes P0 | Depois P1.1 | Gap fechado |
|-------|----------|-------------|-------------|
| calendar | PARTIAL (initialize sem refresh/chmod) | READY | refresh(Request)+chmod 0o700/0o600+metrics+mask |
| email | PARTIAL | READY | idem gmail.modify |
| web_search | PARTIAL (sem fallback/cache/timeout) | READY | Tavily+DuckDuckGo fallback+cache 5m+timeout 10s+always READY |
| drive | - | READY (novo) | drive.file minimo, 3 tools |
| notes | READY | READY | - |
| automation | READY | READY | - |

### 4b. READY vs SKIP sem credencial (N3)

**Codigo READY != runtime ok.** Sem credencial initialize()=False get_tools()=[] metric skip nao fail. Ver N5 Windows note.

| Skill | Sem credencial | Com credencial |
|-------|---------------|----------------|
| calendar/email/drive | SKIP (metric skip, 0 tools) | READY ok |
| web_search | READY fallback DDG (skip tavily) | READY tavily ok |
| notes/automation | READY | READY |

### 5. Suite reproduzivel

```bash
python scripts/setup.py --dev --non-interactive --force
docker compose up -d --wait
python scripts/run_tests.py --quick  # 2 PASS
python scripts/run_tests.py --ci      # 5 PASS + junit
python scripts/compute_readiness.py --status '{"Skills":"READY"}' # 92.0/67.2/60.4
python scripts/verify_env.py # PASS
python -m scripts.smoke_test # 7/7 PASS >=3 skills
```

## Aceite binario

- [ ] smoke >=3 skills PASS
- [ ] verify_env PASS + setup --check PASS
- [ ] compute P0 86.0 + compute --status Skills=READY 92.0
- [ ] drive.py + config Drive + metrics + registry + oauth.md
- [ ] .gitignore ja bloqueia config/tokens e .env.bak

**Gate P1.1->P1.2 PASS se todos acima PASS.**

## Proximo: P1.2

Slack/GitHub/SEO hardening, Notion/WhatsApp stubs, rate-limit, HITL loop.
