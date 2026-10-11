# Documentação

**Para quem usa:** `GUIA_LEIGO_JEFREY.md`, `WHATSAPP.md`, `GOOGLE.md`, `MODELOS.md`.
**Para quem mantém:** `ARQUITETURA.md` (camadas e como migrar), `APP_DESKTOP.md` (janela, bandeja, orbe, reiniciar), `COMO_O_JEFREY_FUNCIONA.md`, `PORTOES.md` (o que precisa passar antes de entregar), `CHECKLIST_LANCAMENTO.md`, `PILOTO.md`, `MELHORIAS.md`, `PESQUISA_JARVIS.md`, `AUDITORIA_2026-10-10.md` (estado real do projeto).
**Para entregar:** `DISTRIBUICAO.md`, `PUBLICAR.md`, `LICENCAS_TERCEIROS.md`.
**Segurança:** `THREAT_MODEL.md`, `AUDITORIA_CIPHER_2026-10.md`, `ADRs/`.
**Opcional:** `CONEXOES_N8N.md`.

O produto é o **modo nativo** (`Jefrey.exe`). O caminho de servidor (Docker/Kubernetes) foi removido; o histórico fica no Git.

## Ferramentas de verificação (em `scripts/`)
| Comando | Para quê |
|---|---|
| `python scripts/verify_installed.py` | 22 verificações do programa instalado |
| `python scripts/check_connectivity.py` | cérebro de IA, Google, Hoje, WhatsApp, voz, atualizações |
| `python scripts/audit_whatsapp.py` | simula a extensão do WhatsApp contra o app em execução |
| `python scripts/bench_chat.py` | velocidade das respostas por tipo de pergunta |
| `python scripts/arch_report.py` | o que ainda está misturado (arquitetura) |
| `python scripts/dead_code.py` | módulos que ninguém importa |
| `scripts/dev/` | `cdp.py` (inspecionar a janela), `shot.ps1` (captura), `vis.ps1` (janelas abertas) |
