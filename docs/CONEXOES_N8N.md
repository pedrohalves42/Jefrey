# CONEXOES N8N — Jefrey 1 programa 7 pecas (F6-3)

Webhooks n8n para Conexoes 1-Clique (sem novo container, reusa jefrey-n8n:5678).

## Workflows a criar em http://localhost:5678

### 1) Enviar WhatsApp/Telegram
- **Workflow name**: jefrey-send-message
- **Trigger**: Webhook POST `/webhook/jefrey-send-message`
- **Body**: `{ to, channel: "whatsapp"|"telegram", text, user_id }`
- **Nodes**:
  - IF channel == whatsapp → WhatsApp Business node (ou HTTP Request para API)
  - IF telegram → Telegram node (bot token em JEFREY_TELEGRAM_BOT_TOKEN)
- **CORS**: n8n ja permite POST de jefrey-api (CIPHER-031)

### 2) Navegar (browser_control)
- **Workflow name**: jefrey-browser
- **Trigger**: Webhook POST `/webhook/jefrey-browser`
- **Body**: `{ url, user_id }`
- **Nodes**: HTTP Request (fetch URL) → HTML extract → Respond with screenshot/text
- **Alternativa local**: MCP stdio playwright direto em jefrey-api (AutomationSkill browser_control) sem n8n

## Teste
```bash
curl -X POST http://localhost:8000/connections/send -H "Authorization: Bearer <token>" -H "X-User-Id: demo" -d '{"to":"+5511999999999","channel":"whatsapp","text":"oi via Jefrey"}'
curl -X POST http://localhost:8000/connections/test -H "Authorization: Bearer <token>" -d '{}'
```

## Env vars
- `JEFREY_N8N_WEBHOOK_URL=http://jefrey-n8n:5678/webhook/jefrey-send-message`
- `JEFREY_TAVILY_API_KEY` para busca web real (fallback DuckDuckGo sem key)
