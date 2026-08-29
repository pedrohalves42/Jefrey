# Auditoria de Dependências do Jefrey

## Objetivo
Validar todas dependências do projeto, garantir que estão atualizadas, seguras e compatíveis.

## Escopo

### Dependências a Auditar

#### Python Dependencies
**Arquivos:** requirements.txt, pyproject.toml

**Dependências Principais:**
```
# Core
python = "^3.12"
fastapi = "^0.100.0"
uvicorn = "^0.27.0"
pydantic = "^2.0.0"

# LLM e Agents
openai = "^1.0.0"

# Banco de Dados
sqlalchemy = "^2.0.0"
psycopg2-binary = "^2.9.0"
redis = "^5.0.0"
pgvector = "^0.2.0"

# Ferramentas
requests = "^2.31.0"

# Segurança
pydantic-settings = "^2.0.0"

# Testes
pytest = "^8.0.0"

# Desenvolvimento
black = "^24.0.0"
```

#### Node.js Dependencies (n8n)
**Arquivo:** package.json

**Dependências Principais:**
```json
{
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.4.0",
    "n8n": "^1.0.0"
  }
}
```

#### Banco de Dados
- PostgreSQL: 15+
- pgvector: Extensão instalada
- Redis: 7+

#### APIs Externas
- OpenAI API: Chave configurada
- Google APIs: Credenciais OAuth configuradas
- Tavily API: Chave configurada

## Metodologia

### 1 Listar Todas Dependências
```bash
# Python
pip freeze > current_requirements.txt
cat requirements.txt
cat pyproject.toml

# Node.js
npm list --depth=0
cat package.json

# Docker
docker-compose config
```

### 2 Verificar Versões
Para cada dependência:
- Versão atual instalada
- Versão mínima requerida
- Última versão estável
- Vulnerabilidades conhecidas

### 3 Verificar Vulnerabilidades
```bash
# Python
pip install safety pip-audit
safety check --full-report
pip-audit

# Node.js
npm audit
npm audit fix

# Docker
trivy image <imagem>
```

### 4 Validar Funcionamento
```python
# Testar importação
try:
    import fastapi
    print(f"FastAPI {fastapi.__version__} OK")
except ImportError as e:
    print(f"FastAPI não instalado: {e}")
```

## Checklist de Auditoria

### Fase 1: Python Dependencies (1-2 dias)

#### 1.1 Listar e Categorizar
```bash
pip freeze > dependencies.txt
cat dependencies.txt | grep -E "^fastapi|^openai|^sqlalchemy|^redis|^pydantic" > core_deps.txt
cat dependencies.txt | grep -E "^pytest|^black" > dev_deps.txt
```

#### 1.2 Verificar Versões

| Dependência | Versão Atual | Versão Mínima | Status |
|-------------|--------------|---------------|--------|
| Python | 3.12+ | 3.12 | ✅ |
| FastAPI | 0.109.1 | 0.100.0 | ✅ |
| OpenAI | 1.12.0 | 1.0.0 | ✅ |
| SQLAlchemy | 2.0.25 | 2.0.0 | ✅ |
| Redis | 5.0.1 | 5.0.0 | ✅ |
| Pydantic | 2.6.4 | 2.0.0 | ✅ |
| Pytest | 8.1.1 | 8.0.0 | ✅ |
| Black | 24.3.0 | 24.0.0 | ✅ |

#### 1.3 Verificar Vulnerabilidades
```bash
safety check
pip-audit
```

#### 1.4 Validar Funcionamento
```python
import fastapi, openai, sqlalchemy, redis, pydantic
print("Todas dependências Python OK")
```

### Fase 2: Node.js Dependencies (1 dia)

#### 2.1 Listar Dependências
```bash
cd n8n_directory || echo "n8n não encontrado"
cat package.json
npm list --depth=0
```

#### 2.2 Verificar Versões

| Dependência | Versão Atual | Versão Mínima | Status |
|-------------|--------------|---------------|--------|
| @modelcontextprotocol/sdk | 0.4.0 | 0.4.0 | ✅ |
| n8n | 1.42.0 | 1.0.0 | ✅ |

#### 2.3 Verificar Vulnerabilidades
```bash
npm audit
npm audit fix
```

#### 2.4 Validar Funcionamento
```bash
node -e "const mcp = require('@modelcontextprotocol/sdk'); console.log('MCP SDK OK')"
n8n --version
```

### Fase 3: Banco de Dados (1 dia)

#### 3.1 PostgreSQL
```bash
psql --version
psql -U postgres -c "SELECT version();"
```

Versão mínima: 15+

#### 3.2 Redis
```bash
redis-cli --version
redis-cli ping
```

Versão mínima: 7+

### Fase 4: APIs Externas (1 dia)

#### 4.1 OpenAI API
```bash
cat .env | grep OPENAI_API_KEY
echo $OPENAI_API_KEY

python -c "
from openai import OpenAI
client = OpenAI(api_key='$OPENAI_API_KEY')
response = client.models.list()
print('OpenAI API conectado:', len(response.data) > 0)
"
```

#### 4.2 Google APIs
```bash
cat .env | grep -E "GOOGLE_CLIENT_ID|GOOGLE_CLIENT_SECRET"
```

### Fase 5: Docker Dependencies (1 dia)

#### 5.1 Verificar Imagens
```bash
cat docker-compose.yml | grep "image:"

# Verificar vulnerabilidades
trivy image ankane/pgvector:latest
trivy image redis:7-alpine
trivy image python:3.12-slim
```

#### 5.2 Validar Configuração
```bash
docker-compose config
docker-compose build --no-cache
docker-compose up -d
```

### Fase 6: Atualização (2 dias)

#### 6.1 Atualizar Dependências
```bash
pip install --upgrade -r requirements.txt
pip install --upgrade fastapi openai sqlalchemy pydantic

pip freeze > updated_requirements.txt
diff requirements.txt updated_requirements.txt
```

#### 6.2 Padronizar Versões
Criar requirements.lock com versões específicas:
```
fastapi==0.109.1
openai==1.12.0
sqlalchemy==2.0.25
pydantic==2.6.4
redis==5.0.1
psycopg2-binary==2.9.9
pgvector==0.2.4
```

#### 6.3 Documentar Dependências
Criar DEPENDENCIES.md com:
- Versões mínimas requeridas
- Versões recomendadas
- Vulnerabilidades conhecidas
- Instruções de atualização

## Relatório de Auditoria

Para cada dependência:

```markdown
## Dependência: [nome]

### Informações
- Nome: [nome]
- Versão Atual: [versão]
- Versão Mínima Requerida: [versão]
- Última Versão: [versão]
- Categoria: [core/dev/utils/api]

### Validação
- [ ] Instalada corretamente
- [ ] Versão compatível
- [ ] Sem vulnerabilidades críticas
- [ ] Funcionamento testado

### Problemas Encontrados
1 Problema: [descrição]
   - Severidade: [Baixa/Média/Alta]
   - Impacto: [descrição]
   - Solução: [sugestão]

### Status Final: [APROVADO / ATUALIZAR / SUBSTITUIR]
```

## Problemas Críticos

### Críticos
1 Versão antiga de dependência crítica
2 Vulnerabilidade crítica em dependência
3 Dependência ausente
4 Chave API inválida
5 Banco de dados não inicializado

### Médios
1 Dependências desatualizadas
2 Vulnerabilidades de baixa severidade
3 Versões conflitantes
4 Documentação incompleta

### Baixos
1 Dependências de desenvolvimento não usadas
2 Versões muito específicas sem justificativa

## Plano de Ação

### Semana 1: Resolver Problemas Críticos
- Atualizar dependências críticas
- Corrigir vulnerabilidades
- Validar chaves de API
- Instalar extensão pgvector

### Semana 2: Padronização
- Criar requirements.lock
- Padronizar versões
- Documentar dependências
- Configurar dependabot

### Semana 3: Validação Completa
- Testar todas dependências
- Validar compatibilidade
- Testar em ambiente limpo
- Validar em Docker