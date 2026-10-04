# Frontend Jefrey - Guia de Desenvolvimento

## Visão Geral

O frontend do Jefrey é uma aplicação React/Vite moderna com:
- React 18 + TypeScript
- TailwindCSS para estilização
- Radix UI para componentes
- React Router para navegação
- TanStack Query para gerenciamento de estado
- Framer Motion para animações

## Estrutura

```
ui/
├── src/
│   ├── components/       # Componentes reutilizáveis
│   │   ├── ui/          # Componentes Radix UI
│   │   ├── AuthButton.tsx
│   │   ├── VoiceButton.tsx
│   │   └── ...
│   ├── pages/           # Páginas principais
│   │   ├── Chat.tsx
│   │   ├── Memory.tsx
│   │   └── ...
│   ├── lib/             # Utilitários
│   │   └── api.ts       # Cliente API
│   ├── hooks/           # Custom hooks
│   └── main.tsx         # Entry point
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## Desenvolvimento Local

### 1. Instalar Dependências

```bash
cd ui
npm install
```

### 2. Iniciar Servidor de Desenvolvimento

```bash
npm run dev
```

O frontend estará disponível em `http://localhost:5173`

O Vite proxy automaticamente as requisições da API para `http://localhost:8000`

### 3. Configurar Backend

Certifique-se de que o backend está rodando:

```bash
# Em outra terminal
cd ..
docker compose up jefrey-api postgres redis ollama
```

## Build para Produção

### 1. Build Local

```bash
cd ui
npm run build
```

Isso gera a pasta `ui/dist/` com o frontend otimizado.

### 2. Build via Docker

```bash
docker compose build frontend
docker compose up frontend
```

O frontend estará disponível em `http://localhost:3001`

## Conexão com API

### Cliente API (`src/lib/api.ts`)

O frontend usa um cliente API centralizado que:

1. Gerencia tokens Bearer automaticamente
2. Adiciona headers de autenticação (`Authorization`, `X-User-Id`)
3. Trata erros HTTP de forma consistente
4. Implementa fail-closed (Axiom #1)

### Endpoints da API

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Health check |
| `/auth/dev-token` | POST | Obter token dev (apenas desenvolvimento) |
| `/chat` | POST | Enviar mensagem |
| `/chat/stream` | POST | Streaming SSE |
| `/chat/status/{thread_id}` | GET | Status de chat assíncrono |
| `/memory` | GET/POST | Memória semântica |
| `/approvals` | GET/POST | Aprovações HITL |

### Exemplo de Uso

```typescript
import { apiFetch, getToken, getUserId } from "@/lib/api"

// Enviar mensagem
const response = await apiFetch("/chat", {
  method: "POST",
  body: JSON.stringify({
    message: "Olá Jefrey",
    thread_id: "thread-123",
    user_id: getUserId()
  })
})

const data = await response.json()
console.log(data.response)
```

## Autenticação

### Token Dev (Desenvolvimento)

O frontend obtém automaticamente um token dev via `/auth/dev-token`:

```typescript
await ensureDevToken()
```

Este token é salvo em `localStorage` como `jefrey_token`.

### Google OAuth2 (Produção)

Para usar Google OAuth2:

1. Configure as variáveis de ambiente:
   ```bash
   JEFREY_OAUTH__CLIENT_ID="seu-client-id.apps.googleusercontent.com"
   JEFREY_OAUTH__CLIENT_SECRET="seu-client-secret"
   ```

2. Use o endpoint `/auth/google/login` para iniciar o flow OAuth2

3. O callback `/auth/google/callback` salva o token no PostgreSQL

## Estilização

### Glassmorphism UI

O frontend usa glassmorphism inspirado no Open-Higgsfield-AI:

```tsx
<Card className="glass border-cyan-500/20">
  <CardContent>
    {/* Conteúdo com blur e transparência */}
  </CardContent>
</Card>
```

### Dark Mode

O dark mode é o padrão. Cores baseadas em cyan/preto:

```tsx
<div className="bg-background text-foreground">
  {/* Background escuro com cyan para acentos */}
</div>
```

## Componentes Principais

### Chat (`src/pages/Chat.tsx`)

- Interface de chat com streaming SSE
- Suporte a voz (STT/TTS)
- Indicador de estado (thinking, speaking, idle)
- Histórico de mensagens

### Memory (`src/pages/Memory.tsx`)

- Busca semântica
- Adicionar memórias
- Visualização de hits

### Approvals (`src/pages/Approvals.tsx`)

- Listar aprovações pendentes
- Aprovar/rejeitar ações
- HITL (Human-in-the-Loop)

## Troubleshooting

### Erro: "Conectando automaticamente..."

**Causa:** Token dev não obtido ou expirou

**Solução:**
1. Verifique se o backend está rodando
2. Vá em Settings > Obter token dev
3. Ou use `ensureDevToken()` no console

### Erro: "LLM offline"

**Causa:** Ollama não está rodando

**Solução:**
```bash
docker compose up ollama
# Ou local:
ollama serve
ollama pull qwen2.5:0.5b
```

### Erro: "CORS"

**Causa:** CORS não configurado no backend

**Solução:** Configure CORS em `src/jefrey/api/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Próximos Passos

- [ ] Adicionar testes E2E com Playwright
- [ ] Implementar glassmorphism UI completo
- [ ] Adicionar studio-based workflow (Chat Studio, Memory Studio)
- [ ] Implementar Upload History
- [ ] Adicionar Generation History
- [ ] Melhorar responsividade mobile
