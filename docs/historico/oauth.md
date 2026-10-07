# OAuth Google - Jefrey P1.1

Este guia descreve como configurar OAuth para Calendar / Gmail / Drive (escopo minimo).

## 1. Criar credenciais no Google Cloud

1. Acesse https://console.cloud.google.com
2. Crie projeto ou selecione existente
3. APIs & Services -> Library -> Enable:
   - Google Calendar API
   - Gmail API
   - Google Drive API
4. Credentials -> Create Credentials -> OAuth Client ID
   - Application type: Desktop app
   - Name: Jefrey Local
5. Download JSON

## 2. Salvar credenciais localmente (CIPHER-002, 0o700)

```bash
mkdir -p config/credentials config/tokens
# Windows: icacls equivalente; setup.py cria dirs com 0o700 quando possivel
cp ~/Downloads/client_secret_*.json config/credentials/google_calendar.json
cp ~/Downloads/client_secret_*.json config/credentials/gmail.json
cp ~/Downloads/client_secret_*.json config/credentials/google_drive.json
# ou use um unico arquivo e aponte via .env:
# JEFREY_INTEGRATIONS__GOOGLE_CALENDAR__CREDENTIALS_FILE=config/credentials/google_calendar.json
```

Nunca commite `config/credentials/*.json` ou `config/tokens/*.json` - ja em .gitignore.

## 3. Autorizar (gera token 0o600)

Na primeira vez que a skill inicializar, ela abre o navegador para autorizar:

```bash
python -m scripts.smoke_test
# ou force flow:
python -c "from src.jefrey.skills.calendar import CalendarSkill; s=CalendarSkill(); s.initialize()"
```

Token salvo em `config/tokens/google_calendar_token.json` (0o600) com refresh_token.

## 4. Refresh automatico

`CalendarSkill.initialize()` / `EmailSkill` / `DriveSkill` fazem:
- `Credentials.from_authorized_user_file(token_file, SCOPES)`
- se `expired and refresh_token`: `creds.refresh(Request())` + metric `jefrey_oauth_refresh_total`

## 5. Revogar

```bash
# revoga no Google e apaga local
curl -X POST "https://oauth2.googleapis.com/revoke?token=$(jq -r .refresh_token config/tokens/google_calendar_token.json)"
rm config/tokens/google_calendar_token.json
```

## 6. Escopos (least privilege - Anderson)

- Calendar: `https://www.googleapis.com/auth/calendar` (cria/edita/list)
- Gmail: `https://www.googleapis.com/auth/gmail.modify` (ler/enviar/modify, nao full)
- Drive: `https://www.googleapis.com/auth/drive.file` (apenas arquivos criados pelo app, nao drive full)

> **Nota Windows (N5):** `config/tokens` perms `777 != 700` e WARN nao FAIL. `setup.py` tenta `chmod 0o700` mas icacls nao reflete POSIX. Em Linux 0o700/0o600 obrigatorios (CIPHER-002).

## 7. CI sem credencial

Sem `config/credentials/*.json`, `initialize()` retorna False, `get_tools()` retorna [], smoke registra SKIP nao FAIL. CI passa com `>=3 skills` (notes+automation+web_search fallback).

## 8. Troubleshooting

- `google-api-python-client nao instalado`: pip install google-api-python-client google-auth-oauthlib
- `invalid_grant`: token expirado sem refresh_token - apague token e reautorize
- `accessNotConfigured`: API nao habilitada no projeto
