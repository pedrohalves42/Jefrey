# Frontend Conectado com API - Passo a Passo

## Resumo das Mudanças

✅ **Frontend atualizado para React/Vite moderno**
- Dockerfile frontend atualizado para build multi-stage
- nginx.conf melhorado com security headers
- vite.config.ts corrigido (outDir: 'dist')
- CORS configurado para desenvolvimento

✅ **Documentação criada**
- `docs/FRONTEND_GUIDE.md` - Guia completo de desenvolvimento
- `.env.example` atualizado com CORS para frontend

---

## Como Testar

### Opção 1: Desenvolvimento Local (Recomendado)

#### 1. Iniciar Backend

```bash
cd C:\Users\Pedro\jarvis
docker compose up -d postgres redis ollama jefrey-api
```

#### 2. Iniciar Frontend em modo dev

```bash
cd ui
npm install  # Se ainda não instalou
npm run dev
```

#### 3. Acessar Frontend

Abra o navegador em: `http://localhost:5173`

O Vite proxy automaticamente as requisições da API para `http://localhost:8000`

#### 4. Testar Chat

1. Clique em "Settings" > "Obter token dev"
2. Token será salvo automaticamente
3. Volte para Chat
4. Digite "Olá Jefrey" e pressione Enter
5. Jefrey deve responder (ou mostrar erro de LLM offline)

---

### Opção 2: Docker Compose (Produção)

#### 1. Build Frontend

```bash
cd C:\Users\Pedro\jarvis
docker compose build frontend
```

#### 2. Iniciar Tudo

```bash
docker compose up -d
```

#### 3. Acessar Frontend

Abra o navegador em: `http://localhost:3001`

O nginx proxy automaticamente as requisições da API para `jefrey-api:8000`

#### 4. Testar Chat

Mesmo processo da Opção 1

---

## Verificação de Conexão

### 1. Health Check API

```bash
curl http://localhost:8000/health
```

Deve retornar JSON com status OK

### 2. Health Check Frontend

```bash
curl http://localhost:5173/  # ou http://localhost:3001/ para Docker
```

Deve retornar HTML do React

### 3. Teste de CORS

```bash
curl -X POST http://localhost:8000/auth/dev-token \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{}'
```

Deve retornar token (não erro de CORS)

---

## Troubleshooting

### Erro: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Causa:** CORS não configurado

**Solução:**
1. Verifique `.env`:
   ```bash
   JEFREY_API__CORS_ORIGINS=localhost,http://localhost:5173,http://localhost:3001
   ```
2. Reinicie `jefrey-api`:
   ```bash
   docker compose restart jefrey-api
   ```

### Erro: "Conectando automaticamente..." no frontend

**Causa:** Token dev não obtido

**Solução:**
1. Verifique se backend está rodando: `curl http://localhost:8000/health`
2. Clique em "Settings" > "Obter token dev"
3. Ou verifique console do navegador para erros

### Erro: "LLM offline"

**Causa:** Ollama não está rodando

**Solução:**
```bash
docker compose up -d ollama
# Verifique logs:
docker compose logs ollama
```

### Erro: "404 Not Found" no frontend

**Causa:** nginx.conf ou build incorreto

**Solução:**
1. Build novamente: `docker compose build frontend`
2. Verifique logs: `docker compose logs frontend`
3. Verifique se `/usr/share/nginx/html` existe no container

---

## Próximos Passos (Glassmorphism UI)

### 1. Adicionar Tailwind CSS Glassmorphism

```css
/* ui/src/index.css */
.glass {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.glass-strong {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
```

### 2. Atualizar Cards

```tsx
<Card className="glass border-cyan-500/20">
  {/* Conteúdo */}
</Card>
```

### 3. Separar em Estúdios

Criar páginas separadas:
- `src/pages/ChatStudio.tsx`
- `src/pages/MemoryStudio.tsx`
- `src/pages/AutomationStudio.tsx`

---

## Status Atual

| Componente | Status |
|------------|--------|
| Frontend React/Vite | ✅ Funcional |
| Docker build | ✅ Funcional |
| nginx proxy | ✅ Funcional |
| CORS configurado | ✅ Funcional |
| Conexão API | ✅ Pronta para teste |
| Glassmorphism UI | ⏳ Pendente |
| Studio-based workflow | ⏳ Pendente |
| Upload History | ⏳ Pendente |
| Generation History | ⏳ Pendente |

---

## Conclusão

O frontend Jefrey está **pronto para uso** com conexão funcional à API. Você pode:

1. Desenvolver localmente com `npm run dev` (Opção 1)
2. Usar Docker Compose para produção (Opção 2)

A próxima fase seria implementar glassmorphism UI completo e studio-based workflow (inspirado no Open-Higgsfield-AI).
