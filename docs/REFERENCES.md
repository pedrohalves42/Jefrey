# Referências Bibliográficas — Jefrey

Uma seleção de 10 referências fundamentais para o entendimento, evolução e operação de sistemas de agentes IA em produção. Estes livros foram escolhidos com base no que foi construído no Jefrey (P0–P7) e no que ainda precisa ser addressed antes do P8 (especialmente os 5 HIGH security issues).

---

## 1. Designing Data-Intensive Applications — Martin Kleppmann

**Por que ler:** O Jefrey usa Postgres como motor central — checkpointer, 6 camadas de memória, audit log, approvals. Este livro explica com profundidade como bancos relacionais funcionam internamente, quando índices ajudam e quando prejudicam, como transações ACID se comportam sob carga, e por que o pgvector com HNSW é uma escolha sólida. Capítulos sobre replicação e durabilidade são diretamente aplicáveis ao cenário de "Postgres cai e o agente perde estado".

**Aplicação direta no projeto:** entender por que o `AsyncPostgresSaver` precisa de `pool_pre_ping=True`, como o índice HNSW de cosseno se comporta sob concorrência, e quando o Redis como working memory é mais eficiente que o Postgres para dados de sessão curta.

---

## 2. Building LLM Applications — Valentina Alto (O'Reilly, 2024)

**Por que ler:** Cobre a arquitetura de sistemas agenticos do ponto de vista prático — RAG, memória, tool calling, orquestração. Explica as diferenças entre abordagens de memória (buffer, vetorial, episódica) com exemplos reais em Python. O capítulo sobre avaliação de agentes é especialmente relevante porque o Jefrey não tem nenhuma avaliação de qualidade de resposta ainda.

**Aplicação direta no projeto:** estruturar os 6 tipos de memória com critérios claros de quando usar cada camada, e implementar evals básicos para o agente antes de P8.

---

## 3. Fluent Python — Luciano Ramalho (2ª edição, 2022)

**Por que ler:** O código do Jefrey usa descritores (`ToolDescriptor` via `__get__`), decoradores assíncronos (`@timed`, `@counted`), generators assíncronos em `stream()`, e dataclasses com Pydantic. Este livro é a referência definitiva para escrever Python idiomático e eficiente. Os capítulos sobre protocolos, descritores e concorrência com asyncio são diretamente aplicáveis.

**Aplicação direta no projeto:** o `ToolDescriptor.__get__` poderia ser simplificado, o `_RUNNING_TASKS` poderia usar `WeakValueDictionary` para evitar memory leak, e diversos padrões de `asyncio.wait_for` no código poderiam ser mais robustos com o que o livro ensina.

---

## 4. OpenAI Agents SDK — Documentação Oficial + Cookbook

**URL:** `platform.openai.com/docs/guides/agents` e `github.com/openai/openai-agents-python`

**Por que ler:** O Jefrey usa o SDK na versão 0.22 mas a documentação evolui rapidamente. O cookbook oficial tem padrões de handoff entre agentes, uso correto de `RunContextWrapper`, e como estruturar ferramentas com schemas Pydantic. O guia de tracing mostra como ligar observabilidade nativa do SDK com o Prometheus que o Jefrey já tem.

**Aplicação direta no projeto:** o `_guarded_call` do `openai_agent.py` poderia usar o sistema de hooks nativos do SDK em vez de wrapper manual, e o `RunContextWrapper` tem campos que o Jefrey não está usando (`usage`, `model`).

---

## 5. Model Context Protocol — Especificação Oficial 2026-07-28

**URL:** `modelcontextprotocol.io/specification`

**Por que ler:** O MCP evoluiu significativamente. A especificação 2026-07-28 que o Jefrey implementa tem detalhes sobre stateless mode, autorização por header, cache de descoberta e endurecimento de segurança que o código atual não implementa completamente. A seção de segurança explica vetores de ataque via tool injection que são exatamente o CIPHER-011 (prompt injection via MCP externo) que foi mitigado mas não completamente fechado.

**Aplicação direta no projeto:** implementar o `OAuth 2.0 Resource Server` que a spec define para autenticação de servidores MCP em P8, e entender por que o `stateless_http=True` tem implicações de segurança além das de performance.

---

## 6. High Performance Python — Micha Gorelick e Ian Ozsvald (3ª edição)

**Por que ler:** O Jefrey vai processar embeddings de 768 dimensões, fazer buscas vetoriais, e executar múltiplas chamadas ao Postgres e Redis em cada request. Este livro ensina a medir antes de otimizar (profiling com `cProfile`, `line_profiler`), quando usar `asyncio` vs threads vs processos, e como evitar os erros comuns de performance em Python que aparecem apenas sob carga.

**Aplicação direta no projeto:** o `ToolExecutor` tem um loop de polling (`asyncio.sleep(2)`) que sob carga pode acumular coroutines em espera. O livro explica como medir e corrigir esse padrão. Também cobre o custo real de `json.dumps/loads` em hot paths como o `_to_chroma_metadata`.

---

## 7. The Pragmatic Programmer — David Thomas e Andrew Hunt (20th Anniversary Edition)

**Por que ler:** Não é um livro técnico de Python nem de IA — é sobre como pensar sobre software. O conceito de "broken windows" é diretamente aplicável ao projeto: os 5 HIGH abertos antes de P8 são janelas quebradas. O capítulo sobre "tracer bullets" explica por que a abordagem P0→P8 do Jefrey funciona melhor que construir tudo de uma vez. O capítulo sobre testes explica por que `verify_p2.py` precisou de correção (teste que não prova o que diz).

**Aplicação direta no projeto:** criar um checklist de "done" que vai além do critério AXIOM, cobrir o débito técnico de forma sistemática, e estabelecer convenções de código que o time (você + IA) siga consistentemente.

---

## 8. Prometheus: Up & Running — Brian Brazil (O'Reilly)

**Por que ler:** O Jefrey tem 13 métricas implementadas manualmente com `prometheus_client`. Este livro explica como modelar métricas corretamente — a diferença entre Counter, Gauge, Histogram e Summary não é óbvia, e escolher errado cria dashboards enganosos. O capítulo sobre cardinalidade explica por que o Jefrey não deve usar `user_id` como label (o que está correto, mas o livro explica o porquê).

**Aplicação direta no projeto:** os `APPROVALS_CREATED_total` e `TOOLS_BLOCKED_total` poderiam ter labels mais úteis, e o Grafana dashboard de 6 painéis poderia ser expandido com alertas baseados em regras que o livro ensina a escrever.

---

## 9. Security Engineering — Ross Anderson (3ª edição, gratuita online)

**URL:** `cl.cam.ac.uk/~rja14/book.html`

**Por que ler:** O Jefrey implementou RBAC, HITL, audit log, timing-safe comparison e content guard — mas sem um modelo de ameaça formal. Este livro ensina a pensar sobre segurança de forma sistemática: quem são os adversários, quais são os vetores de ataque, como priorizar defesas. O capítulo sobre controle de acesso é a base teórica do que o PolicyEngine implementa empiricamente.

**Aplicação direta no projeto:** criar um `THREAT_MODEL.md` formal antes de P8 que documente os adversários assumidos, os ativos protegidos e as decisões de design de segurança. Isso transforma as decisões implícitas (por que admin bypass existe, por que TTL é 30min) em documentação auditável.

---

## 10. Software Engineering at Google — Winters, Manshreck, Wright (gratuito online)

**URL:** `abseil.io/resources/swe-book`

**Por que ler:** O Jefrey não tem CI/CD, não tem testes de carga, não tem runbooks de operação — tudo isso é P8. Este livro explica como o Google pensa sobre confiabilidade, testes em escala, e o custo real da dívida técnica. O capítulo sobre "toil" é diretamente aplicável: cada vez que você roda `verify_p3b.py` manualmente e faz re-bootstrap do n8n, isso é toil que CI/CD elimina.

**Aplicação direta no projeto:** estruturar o pipeline de CI/CD de P8, definir SLOs para o Jefrey (latência máxima aceitável, disponibilidade mínima), e criar runbooks para os cenários de falha documentados no resumo acima.

---

## Ordem de leitura recomendada

```
AGORA (antes de P8):
  1. MCP Spec 2026-07-28      → fecha gaps de segurança no gateway
  2. OpenAI Agents Cookbook   → melhora openai_agent.py antes de OAuth
  3. Security Engineering cap. 4-8 → modelo de ameaça formal

DURANTE P8:
  4. Prometheus: Up & Running → refina as 13 métricas
  5. Designing Data-Intensive  → otimiza queries e índices sob carga
  6. SWE at Google cap. 11-14 → estrutura CI/CD e runbooks

DEPOIS DE P8 (qualidade contínua):
  7. Fluent Python cap. 19-21 → refatora descritores e async
  8. High Performance Python  → profiling real sob carga
  9. Building LLM Apps        → evals e qualidade de resposta
 10. Pragmatic Programmer     → processo e cultura de desenvolvimento