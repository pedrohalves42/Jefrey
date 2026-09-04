# GUIA LEIGO JEFREY — 1 programa, 7 pecas (F6-5)

> Abra e use em 1 minuto. Sem manual. Se der 401, clique em **Liberar acesso (1s)**.

## 5 passos

1. **Subir**: duplo clique em `start_jefrey.bat` (ou `docker compose up -d --build`) → aguarde 30-45s até 7/7 healthy.
2. **Abrir**: http://localhost:8000 → wizard 3 passos → header mostra **Pronto** verde (token auto). HUD Reactor pulsa 1.0→1.6.
3. **Conversar**: digite “oi” → **Enviar** → resposta em 48s (poll running→complete, qwen2.5:0.5b). Ou clique no **microfone** → fale → TTS toca.
4. **Conexões 1-clique** (abaixo do Chat):
   - 🌐 **Navegar**: cole https://... → Abrir (MCP browser_control ou n8n fallback)
   - 📎 **Arquivo**: arraste arquivo ou cole texto → Salvar em Memória (HNSW m16 ef64, 500MB)
   - 🔍 **Buscar**: digite “IA hoje” → Buscar Web (Tavily + DuckDuckGo)
   - 💬 **Enviar**: escolha WhatsApp/Telegram, para + mensagem → Enviar via n8n webhook
5. **Observar**: aba Observabilidade → 3 luzes gigantes (p95, 7/7, 42 tools) + Grafana http://localhost:3000 (admin / env GRAFANA_PASSWORD) só para dev.

## Tour

Reveja a qualquer momento: http://localhost:8000/?tour=1 — 4 steps (Chat, Voz, Conexões, Observar).

## Troubleshooting

| Sintoma | Causa | Fix |
|---------|-------|-----|
| Badge “conectando…” fica | JEFREY_ENV != dev bloqueia dev-token 403 | Em prod cole JWT em Settings → Salvar |
| POST /chat 401 | token expirou | Clique **Liberar acesso (1s)** no erro |
| Voz “Sem token” | sem Bearer | Header deve mostrar **Pronto**; se não, Settings → Obter token dev |
| n8n Enviar 502 webhook nao configurado | workflow não criado | Veja docs/CONEXOES_N8N.md → crie webhook /webhook/jefrey-send-message em http://localhost:5678 |

## Stack 7 peças (1 programa, Axiom #7)

jefrey-api:8000 (UI + /chat + /stt /tts), postgres:5432 pgvector HNSW, redis:6379 Streams DLQ 5000, mcp:8001, n8n:5678, prometheus:9090, grafana:3000 — 175/175 validado.

*F6-5 2026-09-04 — v1.5.0-leigo-100*
