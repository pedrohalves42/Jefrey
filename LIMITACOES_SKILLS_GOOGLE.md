# Skills Google (Calendar, Gmail, Drive) - OAuth Multi-Tenant

## Status: ✅ IMPLEMENTADO - OAuth Multi-Tenant Completo

As skills Google Calendar, Gmail e Google Drive agora têm **suporte completo a OAuth2 multi-tenant**.

## Implementação (CIPHER-001 FIX)

### O que foi implementado:

1. ✅ **Tabela `oauth_tokens` no PostgreSQL** - Cada user_id tem seu próprio token
2. ✅ **Endpoint `/auth/google/callback`** - OAuth2 flow por usuário (salva token no PostgreSQL)
3. ✅ **Endpoint `/auth/oauth-token/{provider}`** - Obtém token específico do user_id
4. ✅ **Endpoint `POST /auth/oauth-token/{provider}`** - Salva token manualmente (testes)
5. ✅ **Skills Google (calendar, email, drive)** - Buscam token específico do user_id
6. ✅ **Refresh token automático** - Tokens expirados são renovados automaticamente
7. ✅ **Configuração** - `client_id` e `client_secret` por provider

### Isolamento Multi-Tenant

- Cada usuário tem seu próprio token OAuth2 salvo no PostgreSQL
- Skills Google usam `_get_credentials_for_user(user_id)` para obter token específico
- Se o token expirar, é feito refresh automático via `refresh_token`
- Fallback para single-tenant (filesystem) apenas se token não encontrado no PostgreSQL

## Como Usar

### 1. Configurar Google OAuth2

Defina as variáveis de ambiente (ou use valores padrão para dev):

```bash
export JEFREY_OAUTH__CLIENT_ID="seu-client-id.apps.googleusercontent.com"
export JEFREY_OAUTH__CLIENT_SECRET="seu-client-secret"
export JEFREY_OAUTH__REDIRECT_URIS="http://localhost:8000/auth/google/callback"
```

### 2. Fazer Login com Google

```bash
# Usuário faz login com Google OAuth2
curl -X POST "http://localhost:8000/auth/google/login" \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "http://localhost:8000/auth/google/callback"}'
```

O usuário será redirecionado para o Google, faz login, e é redirecionado de volta. O token é salvo automaticamente no PostgreSQL.

### 3. Usar Skills Google

As skills Google agora recebem `user_id` como parâmetro e usam o token específico desse usuário:

```python
# Exemplo: listar eventos do calendário
await calendar.list_events(user_id="user123")
```

O skill busca o token OAuth2 do PostgreSQL para `user_id="user123"` e usa-o para acessar o Google Calendar desse usuário.

## Arquivos Modificados

- `src/jefrey/core/models.py` - Modelo `OAuthToken`
- `src/jefrey/core/db.py` - Setup da tabela `oauth_tokens`
- `src/jefrey/api/auth.py` - Endpoints OAuth2 (`/auth/google/callback`, `/auth/oauth-token/{provider}`)
- `src/jefrey/skills/calendar.py` - `_get_credentials_for_user(user_id)` implementado
- `src/jefrey/skills/email.py` - `_get_credentials_for_user(user_id)` implementado
- `src/jefrey/skills/drive.py` - `_get_credentials_for_user(user_id)` implementado
- `src/jefrey/core/config.py` - `client_id` e `client_secret` por provider

## Testes

```bash
python scripts/smoke_test.py
# Resultado: 7/7 PASS - Skills: 6 carregadas, 34 ferramentas
```

## Referências

- Axiom #2: ISOLAMENTO - Cada user_id tem seu próprio token OAuth2
- CIPHER-001: Skills Google isoladas por tenant (FIXED)
- DDIA cap 6: Partitioning por tenant

