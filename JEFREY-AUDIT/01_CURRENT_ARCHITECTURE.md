# Arquitetura Atual do Jefrey

## Visão Geral

Baseado no material fornecido, a arquitetura atual do Jefrey possui os seguintes componentes principais:

### Componentes Existentes

#### Estrutura de Projeto
- Backend: Python 3.12+, FastAPI, OpenAI Agents SDK
- Banco de Dados: PostgreSQL + pgvector (planejado) / ChromaDB (atual)
- Cache: Redis
- Orquestração: n8n (planejado)
- MCP: MCP Server/Client (planejado)
- Voz: OpenAI Realtime (planejado) / faster-whisper + Piper (fallback)
- Observabilidade: OpenTelemetry/Prometheus (planejado)

#### Skills Implementadas
- notes: Sistema de criação, leitura, busca e gerenciamento de notas
- web_search: Integração com APIs de busca (Tavily/Google)
- calendar: Estrutura para OAuth com Google Calendar (pendente)
- gmail: Estrutura para OAuth com Gmail (pendente)

#### Memória (6 Camadas)
- Working Memory: Contexto atual da conversa
- Episodic Memory: Histórico de eventos
- Semantic Memory: Conhecimento armazenado (embeddings)
- Preference Memory: Preferências do usuário
- Procedural Memory: Como executar tarefas
- Operational Memory: Estado operacional do sistema

## Problemas Identificados

1 Falta de padronização
   - Skills usam estruturas diferentes
   - Sistema de memória não padronizado
   - Ferramentas sem schema comum
   - Níveis de risco não definidos

2 Segurança insuficiente
   - RBAC não implementado
   - Policy Engine ausente
   - HITL não estruturado
   - Guardrails de entrada/saída não implementados
   - Autorização dinâmica não existe

3 Integrações incompletas
   - OAuth para Google Calendar não implementado
   - OAuth para Gmail não implementado
   - MCP não estruturado como camada principal
   - n8n não integrado como executor

4 Observabilidade limitada
   - Logging básico
   - Métricas não implementadas
   - Traces ausentes
   - Alertas não configurados

5 Testes insuficientes
   - Testes unitários básicos
   - Testes de integração limitados
   - Testes de segurança ausentes
   - Testes E2E não existem

## Arquitetura Alvo

Jefrey Agent Core -> Memory System (6 camadas) -> Tool Registry -> Policy Engine -> MCP Layer -> n8n Workflows

### Componentes Principais
1 Agent Core: Orquestração principal com OpenAI Agents SDK e FastAPI
2 Memory System: 6 camadas de memória usando PostgreSQL+pgvector e Redis
3 Tool Registry: Sistema de registro de ferramentas com níveis de risco
4 Policy Engine: RBAC, classificação de risco e workflows de aprovação
5 MCP Layer: Interface padrão para ferramentas usando MCP SDK
6 n8n Workflows: Executor de automações com workflows padronizados
7 Authentication System: JWT/OAuth2 com RBAC
8 HITL System: Aprovações manuais para ações de alto risco
9 Observability: OpenTelemetry, Prometheus e Grafana

## Critérios de Sucesso

### Funcionalidade
- Agente responde de forma contextual por N turnos
- Memória de longo prazo funciona corretamente
- Ferramentas são chamadas com validação
- Workflows n8n executam conforme esperado
- Interface web permite interação completa

### Segurança
- RBAC implementado e testado
- Policy Engine avalia todas as chamadas de ferramentas
- HITL requer aprovação para ações de alto risco
- Guardrails bloqueiam injeção de prompt
- Audit logs registram todas as ações críticas

### Confiabilidade
- Sistema recupera de falhas
- Retry policies implementadas
- Backup e restore testados
- Monitoramento proativo

### Performance
- Latência de resposta aceitável (< 2s para chat)
- Throughput adequado para uso simultâneo
- Uso eficiente de recursos

### Manutenibilidade
- Código documentado
- Testes cobrem funcionalidades críticas
- Logging adequado para debugging
- Configuração externa (não hardcoded)

## Plano de Ação

### Fase 1: Auditoria e Estabilização (P0)
1 Executar auditoria detalhada de código
2 Corrigir problemas críticos de importação
3 Criar ambiente Docker reproduzível
4 Implementar testes básicos
5 Padronizar sistema de memória
6 Estruturar sistema de segurança inicial

### Fase 2: Arquitetura Alvo (P1-P2)
1 Reestruturar projeto para arquitetura alvo
2 Implementar Tool Registry com níveis de risco
3 Criar Policy Engine com RBAC
4 Estruturar MCP Layer
5 Integrar n8n como executor
6 Implementar HITL System

### Fase 3: Funcionalidades Completas (P3-P5)
1 Implementar pipeline de voz
2 Completar integrações OAuth
3 Desenvolver interface web completa
4 Implementar observabilidade completa
5 Criar workflows n8n padronizados
6 Implementar testes de segurança

### Fase 4: Produção (P6+)
1 Deploy em ambiente de produção
2 Configurar backup e restore
3 Implementar CI/CD
4 Otimizar performance
5 Documentar completamente