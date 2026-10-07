# 📋 GUIA DE CREDENCIAIS E PLACEHOLDERS - Jefrey AI Production

## 🔑 **Credenciais Necessárias (Você deve fornecer)**

### **1. Domínio e DNS**
| Placeholder | Onde alterar | Onde conseguir |
|-------------|--------------|----------------|
| `jefrey.your-domain.com` | `k8s/overlays/prod/certificate.yaml`, `k8s/base/ingress.yaml` | Seu provedor DNS (Cloudflare, Route53, GoDaddy, etc.) |
| `monitoring.jefrey.your-domain.com` | `k8s/base/ingress.yaml` | Mesmo provedor DNS |
| `admin@your-domain.com` | `k8s/base/cert-manager.yaml` (2x) | Seu email para Let's Encrypt |

**Ação**: Crie registros A/CNAME no seu DNS apontando para o IP do Load Balancer do cluster.

---

### **2. AWS Secrets Manager (ou Vault/Azure/GCP/1Password)**
| Placeholder | Onde alterar | Onde conseguir |
|-------------|--------------|----------------|
| `region: us-east-1` | `k8s/base/external-secrets.yaml` | AWS Console → Secrets Manager → Region |
| `serviceAccountRef.name` | `k8s/base/external-secrets.yaml` | AWS IAM → Service Account para IRSA |
| `key: jefrey/production` | `k8s/base/external-secrets.yaml` (4x) | AWS Console → Secrets Manager → Secret name |
| `key: jefrey/postgres` | `k8s/base/external-secrets.yaml` | AWS Console → Secrets Manager |
| `key: jefrey/redis` | `k8s/base/external-secrets.yaml` | AWS Console → Secrets Manager |

**Ação**: Crie secrets no AWS Secrets Manager com estes nomes e chaves:
```
jefrey/production:
  DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, FERNET_KEY,
  OAUTH_GOOGLE_CLIENT_ID, OAUTH_GOOGLE_CLIENT_SECRET,
  OAUTH_GITHUB_CLIENT_ID, OAUTH_GITHUB_CLIENT_SECRET,
  MCP_OAUTH_TOKENS, OPENAI_API_KEY, TAVILY_API_KEY,
  ELEVENLABS_API_KEY, N8N_API_KEY, N8N_ENCRYPTION_KEY,
  SLACK_WEBHOOK_URL, PAGERDUTY_KEY, SMTP_PASSWORD

jefrey/postgres:
  POSTGRES_PASSWORD, POSTGRES_USER, POSTGRES_DB

jefrey/redis:
  REDIS_PASSWORD
```

---

### **3. OAuth Providers**
| Provider | Site | O que criar |
|----------|------|-------------|
| **Google** | https://console.cloud.google.com/ | OAuth 2.0 Client ID → Authorized redirect URIs: `https://jefrey.your-domain.com/auth/callback/google` |
| **GitHub** | https://github.com/settings/developers | New OAuth App → Callback: `https://jefrey.your-domain.com/auth/callback/github` |

---

### **4. APIs Externas**
| API | Site | Para que serve |
|-----|------|----------------|
| **OpenAI** | https://platform.openai.com/api-keys | LLM principal (GPT-4o, etc.) |
| **Tavily** | https://tavily.com/ | Web search tool |
| **ElevenLabs** | https://elevenlabs.io/app/settings/api-keys | TTS voice synthesis |
| **Anthropic** (opcional) | https://console.anthropic.com/ | Claude models |

---

### **5. Notificações (Alertmanager)**
| Serviço | Site | O que configurar |
|---------|------|------------------|
| **SMTP** | Seu provedor email (Gmail, SendGrid, SES, etc.) | Host, porta, user, password |
| **Slack** | https://api.slack.com/apps | Incoming Webhook → `#alerts`, `#critical-alerts`, `#warnings`, `#info` |
| **PagerDuty** | https://app.pagerduty.com/ | Service → Integration Key (Events API v2) |

---

### **6. n8n (Workflow Automation)**
| Item | Site |
|------|------|
| `N8N_API_KEY` | n8n UI → User Settings → API Key |
| `N8N_ENCRYPTION_KEY` | Gerar: `openssl rand -hex 32` |

---

### **7. Kubernetes Cluster**
| Provedor | O que precisa |
|----------|---------------|
| **EKS** | `aws eks update-kubeconfig --name <cluster>` |
| **GKE** | `gcloud container clusters get-credentials <cluster>` |
| **AKS** | `az aks get-credentials --name <cluster>` |
| **Kind/Minikube** | Local dev |

---

## ✅ **Checklist de Entrega (Me forneça estes valores)**

```bash
# Domínio
DOMAIN="jefrey.seudominio.com"
MONITORING_DOMAIN="monitoring.jefrey.seudominio.com"
LETSENCRYPT_EMAIL="admin@seudominio.com"

# AWS
AWS_REGION="us-east-1"
AWS_SECRET_NAME_PROD="jefrey/production"
AWS_SECRET_NAME_PG="jefrey/postgres"
AWS_SECRET_NAME_REDIS="jefrey/redis"

# OAuth
GOOGLE_CLIENT_ID="xxx.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="GOCSPX-xxx"
GITHUB_CLIENT_ID="xxx"
GITHUB_CLIENT_SECRET="xxx"

# APIs
OPENAI_API_KEY="sk-xxx"
TAVILY_API_KEY="tvly-xxx"
ELEVENLABS_API_KEY="xxx"

# Alertas
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="alerts@seudominio.com"
SMTP_PASS="xxx"
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx"
PAGERDUTY_KEY="xxx"

# n8n
N8N_API_KEY="xxx"
N8N_ENCRYPTION_KEY="xxx"  # openssl rand -hex 32
```

---

## 🌐 **Sites para Acessar (Resumo Rápido)**

| # | Site | Finalidade |
|---|------|------------|
| 1 | **Cloudflare/Route53/GoDaddy** | DNS records A/CNAME |
| 2 | **AWS Console → Secrets Manager** | Criar 3 secrets |
| 3 | **AWS IAM** | Service Account para IRSA |
| 4 | **Google Cloud Console** | OAuth Client ID |
| 5 | **GitHub Settings → Developers** | OAuth App |
| 6 | **OpenAI Platform** | API Key |
| 7 | **Tavily** | API Key |
| 8 | **ElevenLabs** | API Key |
| 9 | **Slack API** | Incoming Webhooks (4 canais) |
| 10 | **PagerDuty** | Events API v2 Integration Key |
| 11 | **Seu provedor SMTP** | Credenciais SMTP |
| 12 | **n8n UI** | API Key + Encryption Key |

---

## 📝 **Como me passar (escolha uma):**

1. **Arquivo `.env.production`** (não commite!):
```bash
cp .env.example .env.production
# edite com seus valores
```

2. **Variáveis de ambiente** (eu leio via `os.environ`)

3. **Me diga quais você já tem** e eu gero os arquivos finais com seus valores

---

**Quer que eu continue criando os arquivos P1 (smoke tests, staging validation, runbooks) enquanto você prepara as credenciais?**