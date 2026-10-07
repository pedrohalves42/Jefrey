# Guia de Configuração OAuth2 Google para Jefrey

## Pré-requisitos
- Conta Google
- Acesso ao Google Cloud Console

## Passo 1: Criar Projeto no Google Cloud Console

1. Acesse: https://console.cloud.google.com/
2. Clique em "Selecionar um projeto" → "NOVO PROJETO"
3. Nome do projeto: `Jefrey Assistant`
4. Clique em "CRIAR"

## Passo 2: Habilitar Google+ API

1. No menu, vá para: APIs e Serviços → Biblioteca
2. Pesquise: "Google+ API" ou "People API"
3. Clique em "HABILITAR"

## Passo 3: Configurar Tela de Consentimento OAuth

1. Vá para: APIs e Serviços → Tela de consentimento OAuth
2. Selecione: "Externo" → "CRIAR"
3. Preencha os campos obrigatórios:
   - Nome do aplicativo: `Jefrey Assistant`
   - E-mail de suporte: seu e-mail
   - Domínios de autorização: `localhost` (para desenvolvimento)
4. Clique em "SALVAR E CONTINUAR" (pode pular escopo para desenvolvimento)
5. Clique em "SALVAR E CONTINUAR" (pode pular usuários de teste para desenvolvimento)
6. Clique em "SALVAR E CONTINUAR" → "VOLTAR PARA O DASHBOARD"

## Passo 4: Criar Credenciais OAuth2

1. Vá para: APIs e Serviços → Credenciais
2. Clique em "CRIAR CREDENCIAIS" → "ID do cliente OAuth"
3. Tipo de aplicativo: "Aplicativo da Web"
4. Configure:
   - Nome: `Jefrey Web Client`
   - URIs de redirecionamento autorizados:
     - `http://localhost:8000/auth/google/callback`
     - `http://127.0.0.1:8000/auth/google/callback`
     - `http://localhost:3001/auth/google/callback` (Docker)
     - `http://127.0.0.1:3001/auth/google/callback` (Docker)
5. Clique em "CRIAR"
6. Copie o **CLIENT ID** e **CLIENT SECRET**

## Passo 5: Configurar no .env

Adicione ao arquivo `.env`:

```bash
# OAuth2 Google
JEFREY_OAUTH__GOOGLE__CLIENT_ID=seu_client_id_aqui
JEFREY_OAUTH__GOOGLE__CLIENT_SECRET=seu_client_secret_aqui

# Alias para compatibilidade
JEFREY_OAUTH__CLIENT_ID=seu_client_id_aqui
JEFREY_OAUTH__CLIENT_SECRET=seu_client_secret_aqui

# Redirect URI (deve coincidir com o configurado no Google)
JEFREY_OAUTH__REDIRECT_URIS=http://localhost:8000/auth/google/callback
```

## Passo 6: Reiniciar o Backend

```bash
docker compose restart jefrey-api
```

## Passo 7: Testar no Frontend

1. Recarregue o frontend (F5)
2. Clique no botão "Auth" no header
3. Selecione "Google OAuth"
4. Faça login com sua conta Google
5. Você será redirecionado de volta ao Jefrey autenticado

## URIs de Redirecionamento Necessárias

- Desenvolvimento local: `http://localhost:8000/auth/google/callback`
- Docker local: `http://localhost:3001/auth/google/callback`
- Produção: `https://seu-dominio.com/auth/google/callback`

## Segurança

- ⚠️ **NUNCA** comite o `.env` com credenciais reais
- ⚠️ Use sempre `.env.example` com valores de exemplo
- ⚠️ Em produção, use URIs HTTPS válidos
- ⚠️ Configure domínios de autorização adequados em produção

## Troubleshooting

### Erro "redirect_uri_mismatch"
- Verifique se o redirect URI no Google Console corresponde exatamente ao usado na solicitação
- Inclua tanto `localhost` quanto `127.0.0.1`

### Erro "access_denied"
- Verifique se o usuário está nos "Usuários de teste" (se configurado)
- Certifique-se de que a tela de consentimento foi publicada

### Erro "invalid_client"
- Verifique se o CLIENT_ID e CLIENT_SECRET estão corretos no `.env`
- Certifique-se de que as credenciais estão ativas

## Documentação Oficial

- Google OAuth2: https://developers.google.com/identity/protocols/oauth2
- Google Cloud Console: https://console.cloud.google.com/
