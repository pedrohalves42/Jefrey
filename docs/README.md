# Documentação

**Para quem usa:** `GUIA_LEIGO_JEFREY.md`, `WHATSAPP.md`, `GOOGLE.md`, `MODELOS.md`.
**Para quem mantém:** `ARQUITETURA.md` (camadas e como migrar), `APP_DESKTOP.md` (janela, bandeja, orbe, reiniciar), `COMO_O_JEFREY_FUNCIONA.md`, `PORTOES.md` (o que precisa passar antes de entregar), `CHECKLIST_LANCAMENTO.md`, `PILOTO.md`, `MELHORIAS.md`.
**Para entregar:** `DISTRIBUICAO.md`, `PUBLICAR.md`, `LICENCAS_TERCEIROS.md`.
**Segurança:** `THREAT_MODEL.md`, `AUDITORIA_CIPHER_2026-10.md`, `runbook.md`, `runbooks/`.
**Caminho de servidor (Docker/Kubernetes, opcional):** `servidor/`, `SLO*.md`, `PERF_TUNING.md`, `HNSW_TUNING.md`, `METRICS_CARDINALITY.md`, `CONEXOES_N8N.md`.
**Histórico (planos e estudos antigos, só para consulta):** `historico/`.

O caminho oficial do produto é o **modo nativo** (`Jefrey.exe`). O caminho de servidor continua no repositório, mas não é o foco.

## Ferramentas de verificação (em `scripts/`)
| Comando | Para quê |
|---|---|
| `python scripts/verify_installed.py` | 22 verificações do programa instalado |
| `python scripts/check_connectivity.py` | cérebro de IA, Google, Hoje, WhatsApp, voz, atualizações |
| `python scripts/bench_chat.py` | velocidade das respostas por tipo de pergunta |
| `python scripts/arch_report.py` | o que ainda está misturado (arquitetura) |
| `python scripts/dead_code.py` | módulos que ninguém importa |
| `scripts/dev/` | `cdp.py` (inspecionar a janela), `shot.ps1` (captura), `vis.ps1` (janelas abertas) |
