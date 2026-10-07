# Guia de Uso - OAuth2 Multi-Tenant Google Skills

## Visão Geral

O Jefrey agora suporta **OAuth2 multi-tenant completo** para Google Calendar, Gmail e Google Drive. Cada usuário tem seu próprio token OAuth2, garantindo isolamento completo de dados.

## Arquitetura

```
Usuário A ──> Login Google ──> Token salvo no PostgreSQL (user_id=user_a)
           ──> Skills Google usam token do user_a ──> Google Calendar A

Usuário B ──> Login Google ──> Token salvo no PostgreSQL (user_id=user_b)
           ──> Skills Google usam token do user_b ──> Google Calendar B
```

## Configuração

### 1. Criar Google OAuth2 Client

1. Acesse https://console.cloud.google.com
2. Crie um novo projeto ou use existente
3. Acesse "APIs & Services" > "Credentials"
4. Clique em "Create Credentials" > "OAuth client ID"
5. Configure:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
6. Copie `Client ID` e `Client Secret`

### 2. Configurar Variáveis de Ambiente

Adicione ao seu `.env` ou configure como variáveis de ambiente:

```bash
# Google OAuth2
JEFREY_OAUTH__CLIENT_ID="seu-client-id.apps.googleusercontent.com"
JEFREY_OAUTH__CLIENT_SECRET="seu-client-secret"
JEFREY_OAUTH__REDIRECT_URIS="http://localhost:8000/auth/google/callback"

# Google Calendar (opcional - para fallback single-tenant)
JEFREY_INTEGRATIONS__GOOGLE_CALENDAR__CLIENT_ID="seu-client-id.apps.googleusercontent.com"
JEFREY_INTEGRATIONS__GOOGLE_CALENDAR__CLIENT_SECRET="seu-client-secret"

# Gmail (opcional - para fallback single-tenant)
JEFREY_INTEGRATIONS__GMAIL__CLIENT_ID="seu-client-id.apps.googleusercontent.com"
JEFREY_INTEGRATIONS__GMAIL__CLIENT_SECRET="seu-client-secret"

# Google Drive (opcional - para fallback single-tenant)
JEFREY_INTEGRATIONS__GOOGLE_DRIVE__CLIENT_ID="seu-client-id.apps.googleusercontent.com"
JEFREY_INTEGRATIONS__GOOGLE_DRIVE__CLIENT_SECRET="seu-client-secret"
```

## Fluxo de Login

### Opção 1: Via Web Browser (Recomendado)

1. Usuário acessa o frontend do Jefrey
2. Clica em "Login com Google"
3. É redirecionado para o Google OAuth2
4. Faz login e autoriza as permissões
5. É redirecionado de volta para `/auth/google/callback`
6. Token é salvo automaticamente no PostgreSQL

### Opção 2: Via API (Para testes)

```bash
# 1. Iniciar o login
curl -X POST "http://localhost:8000/auth/google/login" \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "http://localhost:8000/auth/google/callback"}'

# 2. Copie a URL de autorização retornada e abra no browser
# 3. Após login, você será redirecionado para /auth/google/callback com o código
# 4. O callback salva o token automaticamente no PostgreSQL
```

### Opção 3: Salvar Token Manualmente (Para testes avançados)

```bash
# Se você já tem um token OAuth2, pode salvar manualmente
curl -X POST "http://localhost:8000/auth/oauth-token/google" \
  -H "Authorization: Bearer seu-dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "seu-user-id",
    "access_token": "seu-access-token",
    "refresh_token": "seu-refresh-token",
    "email": "seu-email@gmail.com",
    "expires_in": 3600
  }'
```

## Usar Skills Google

### Via Chat

```
Usuário: Liste meus eventos de calendário para hoje
Jefrey: [Usa calendar.list_events com user_id do usuário]
```

### Via API

```bash
# Listar eventos do calendário
curl -X POST "http://localhost:8000/chat" \
  -H "Authorization: Bearer seu-dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Liste meus eventos de calendário para hoje"
  }'
```

### Diretamente (com user_id)

```python
from src.jefrey.skills.calendar import CalendarSkill

calendar = CalendarSkill()
calendar.initialize()

# Usar com user_id específico
events = await calendar.list_events(user_id="user123")
```

## Verificar Token Salvo

```bash
# Obter token OAuth2 salvo para um usuário
curl -X GET "http://localhost:8000/auth/oauth-token/google" \
  -H "Authorization: Bearer seu-dev-token"
```

## Refresh Token Automático

Tokens expirados são renovados automaticamente via `refresh_token`. O processo:

1. Skill verifica se o token expirou
2. Se expirou e `refresh_token` existe, faz refresh com Google
3. Atualiza o token no PostgreSQL
4. Usa o novo token

Não há ação manual necessária.

## Troubleshooting

### Erro: "OAuth token não encontrado para user_id"

**Causa:** Usuário não fez login com Google ainda.

**Solução:** Faça login com Google OAuth2 primeiro.

### Erro: "OAuth token expired"

**Causa:** Token expirou e não há `refresh_token`.

**Solução:** Faça login novamente com Google OAuth2.

### Erro: "Google token refresh failed"

**Causa:** `refresh_token` expirou ou foi revogado pelo Google.

**Solução:** Faça login novamente com Google OAuth2.

### Erro: "Credenciais não encontradas"

**Causa:** Variáveis de ambiente não configuradas.

**Solução:** Configure `JEFREY_OAUTH__CLIENT_ID` e `JEFREY_OAUTH__CLIENT_SECRET`.

## Segurança

- Tokens são salvos no PostgreSQL com criptografia futura planejada
- `refresh_token` nunca é retornado em respostas de API
- Cada usuário tem seu próprio token (isolamento completo)
- Tokens expirados são renovados automaticamente

## Próximos Passos

- [ ] Criar frontend UI para login com Google
- [ ] Adicionar criptografia de tokens no PostgreSQL
- [ ] Implementar revogação de tokens
- [ ] Adicionar logs de auditoria para operações OAuth2
