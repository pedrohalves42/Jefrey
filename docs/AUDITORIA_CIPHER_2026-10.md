# Auditoria CIPHER, 04/10/2026

Escopo: ~20,5 mil linhas de Python (`src/jefrey`), interface (`ui/`), empacotamento e dependências.
Método (tudo reproduzível): `ruff` (bugs), `bandit` (segurança estática), `pip-audit` (vulnerabilidades de dependências),
varredura de padrões perigosos, medição de código carregado de verdade, simulação de máquina limpa, ataques reais contra o
servidor e execução da suíte de testes. O que não pude verificar está marcado.

Placar da suíte depois das correções: **667 testes de servidor + 108 de interface passando**; 626 importações do projeto
verificadas; `ruff` sem nomes indefinidos.

## 1. Corrigido nesta auditoria

| # | Gravidade | Achado | Evidência | Correção |
|---|---|---|---|---|
| C-01 | **Alta** | Login Google: o `state` era gerado mas **nunca conferido** (o código dizia "enforce em prod futuro") e não havia PKCE; o retorno é caminho público. Permitia forçar o navegador da vítima a concluir o login com a conta do atacante | leitura de `auth.py` | `state` de uso único com validade de 10 min + PKCE S256; e-mail removido do log; 9 testes (`test_google_oauth_state.py`) |
| C-02 | **Alta** | `/auth/dev-token` e a API acessíveis por **DNS rebinding e CSRF** a partir de qualquer site aberto no navegador | reproduzido: `Host: evil.example` → HTTP 200; `Origin` de outro site → 200 | `LocalGuard` (Host só do PC; Origin só da própria tela; escrita de outro site recusada), agora ligado em **toda execução dev** (antes só no modo nativo). Depois: 400/403 |
| C-03 | Média | `/ws` público (WebSocket sem login) com gerenciador que transmite consultas de memória e ids de usuário a todos os conectados | leitura de `ws.py`/`main.py`; a interface não usa | endpoint e caminho público **removidos** (reintroduzir só com autenticação, nunca token na URL) |
| C-04 | Média | `docker-compose` publicava Postgres, Redis, Ollama (sem senha) e a API para **toda a rede local** | `ports: "5432:5432"` etc. | todas as portas em `127.0.0.1` |
| C-05 | Média | Bugs latentes (nomes indefinidos): `HTTPException` em `connections.browse` (o bloqueio SSRF falharia com `NameError`), `SystemMessage` em `memory.py`, `schedule_memory_cleanup` em `pg_memory.py` (a limpeza por TTL **nunca rodava**, erro engolido), `Final`, anotação `di` | `ruff F821` (8 casos) | imports corrigidos; F821 = 0 |
| C-06 | Baixa | Webhook aceitava qualquer esquema (`file://`), download de modelo sem limite de tempo, e-mail pessoal em log | `bandit B310/B113`, leitura | só `http(s)`; limite de 1 h; e-mail fora do log |
| C-07 | Média | 6 dependências **sem uso** no código concentravam vulnerabilidades (`langgraph`, `langgraph-checkpoint-postgres`, `langchain`, `langchain-community`, `langchain-anthropic`, `langchain-chroma`) | `pip-audit`: 14 avisos em 8 pacotes | removidas de `requirements.txt` e `pyproject.toml`; **prova**: suíte inteira passa com a importação desses pacotes bloqueada |
| C-08 | Baixa | Código morto: 4 módulos que ninguém importa (`executor`, `instrumentation`, `memory_layers`, `openai_agent`, ~900 linhas) e 100+ imports sem uso | grafo de importação | removidos/limpos; uma regressão causada pela limpeza automática (reexportação em `models.py`) foi detectada pelos testes e revertida |
| C-09 | Média | Conexão ao banco sem limite de tempo travava a aplicação (e a listagem de skills) quando o banco estava fora do ar | teste que pendurou | `connect_timeout` de 3 s (Postgres) / 15 s (SQLite) |
| C-10 | Alta (produto) | Sem `.env` o programa **nem iniciava** (`JEFREY_DATABASE__PASSWORD` obrigatório mesmo com SQLite); o endereço do Ollama do Docker ficava gravado e quebrava o chat fora dele | teste de máquina limpa e `.exe` | senha só exigida para Postgres; endereço do Ollama vem do ambiente; teste permanente `test_clean_machine.py` |

Verificado e **sem achado**: sem `eval`/`exec`/`pickle`/`shell=True`/TLS desligado/SQL por concatenação/segredos fixos/CORS
aberto; JWT com HS256 fixo e `exp`, `sub`, `iss` obrigatórios; a interface não usa HTML inseguro (React escapa); limite de 10 mil
caracteres no chat; zip-slip tratado no restore; isolamento por usuário coberto por testes.

## 2. Pendente (por prioridade)

| # | Gravidade | Achado | O que fazer |
|---|---|---|---|
| P-01 | **Alta (produto)** | **Sem Ollama instalado, memória e notas falham com erro 500** (os "embeddings" dependem dele). Quem usa só a nuvem perde a memória | Embeddings independentes: API compatível com OpenAI (OpenAI/OpenRouter, conferir suporte) e, sem internet/chave, alternativa local embutida; degradar com mensagem em vez de 500 |
| P-02 | **Alta (distribuição)** | **Não reproduzível**: `chroma-hnswlib` não instala no Python 3.14; `pyproject` não declara versão de Python; o Docker usa 3.12 e o `.exe` foi gerado com 3.14 | Fixar Python 3.12 (declarar `requires-python`), reconstruir o `.exe` e validar os pacotes em ambiente limpo. Requer instalar o Python 3.12 (download) |
| P-03 | Média | Avisos restantes: `langchain-core` 0.3.86 (2: traversal em carga de prompt, SSRF em contagem de tokens de imagem), `langchain-openai` (SSRF/TOCTOU), `chromadb` 0.6.3 (3: autorização entre contas e `trust_remote_code` do **servidor** Chroma). Pelo que li, **nenhum caminho afetado é usado** (cliente Chroma embutido, sem imagens, sem carga de prompts) | Atualizar `langchain-core`/`openai` para 1.x e validar em Python 3.12 (tentei, mas não consegui validar em 3.14); acompanhar o Chroma |
| P-04 | Média | Texto armazenado (memórias, documentos importados, e no futuro mensagens do WhatsApp) entra no **prompt de sistema** sem moldura; ferramentas de risco médio (`files_write`, `update_note`, `create_workflow`) rodam sem aprovação. Injeção persistente possível | Enquadrar memórias como "dados, não instruções"; para mensagens de terceiros, **nenhuma ferramenta** |
| P-05 | Média | **Sem arquivo de log** no app empacotado (sem console não há suporte possível); sem como fechar o programa (sem ícone de bandeja); se a porta 8000 estiver ocupada, não sobe | Log em `Jefrey\logs`, ícone de bandeja com "Sair", porta alternativa |
| P-06 | Média | Google: credenciais só por `.env` (o cliente não tem), **sem botão "Conectar Google"** na interface, app não verificado | Decidir: lançar sem Gmail/Agenda ou fazer a verificação do Google |
| P-07 | Média | **31% do código (6,5 mil de 20,5 mil linhas) não é carregado no uso real** (MCP ~1,7 mil, eventbus, plugins, visão, modo Postgres) | Separar ou remover o que não faz parte do produto (superfície de ataque e peso do instalador de 466 MB) |
| P-08 | Média | 70 blocos `except ...: pass` engolem erros em silêncio (foi assim que a limpeza de TTL ficou quebrada) | Trocar por log em nível adequado, começando pelos de memória e segurança |
| P-09 | Média | Seleção de ferramentas por **palavra-chave** (feita para modelos pequenos) limita modelos de nuvem: "cotação do dólar hoje" não aciona busca | Com nuvem, oferecer todas as ferramentas |
| P-10 | Baixa | `/metrics` e `/api/status` públicos; MCP escuta em `0.0.0.0` por padrão (`bandit B104`) | Restringir a `127.0.0.1` fora do Docker |
| P-11 | Qualidade | O modelo local leve **erra fatos** (disse "Sydney" para a capital da Austrália) | Limite do modelo, não do código: é um dos motivos de a nuvem ser o padrão |

## 3. O que esta auditoria não cobriu
- Auditoria independente de terceiros (esta é nossa).
- Teste contra o WhatsApp Web e o login do Google reais (exigem contas e o seu celular).
- Código de interface além da leitura de padrões (sem teste de ponta a ponta automatizado com Playwright).
- Vulnerabilidades em dependências **transitivas** do `.exe` e das bibliotecas nativas (só `requirements.txt` foi auditado).
