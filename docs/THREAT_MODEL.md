# Threat Model - Jefrey v1.6

## Adversários Assumeidos

1. **Usuário mal-intencionado** via interface (prompt injection, jailbreak, injeção de comandos)
2. **MCP externo comprometido** - injeção de ferramentas via gateway MCP non-authenticated
3. **Acesso não-autorizado** a ferramentas de alto risco (HIGH/CRITICAL) sem HITL
4. **Vazamento de credenciais** via output do agente, logs ou respostas HTTP
5. **Sessão hijacking** - token/cookie roubado entre requests
6. **Privilege escalation** - guest/user acessar tools reservadas a admin

## Ativos Protegidos

1. **Memória do usuário** - dados pessoais, histórico de conversa, preferências
2. **Chaves de API** - OpenAI, Google Cloud, Gmail, Calendar, integrations externas
3. **Dados corporativos** - notas, eventos, emails, arquivos, memory entries
4. **Identidade do modelo** - não revelar nome de base model, parâmetros internos
5. **Infraestrutura** - Docker containers, rede, portas, serviços conexos

## Vetores de Ataque

| Vetor | Descrição | Mitigação |
|-------|-----------|-----------|
| **Prompt Injection** | Input/user content contendo instruções para ignorar system prompt ou tool output com comandos ocultos | Content guard com regex patterns (CIPHER-032); sanitization FIRST no pipeline |
| **Tool Abuse** | Chamar ferramentas de risco HIGH/CRITICAL sem autorização adequada | RBAC enforcement; HITL approval para HIGH/CRITICAL; Policy Engine decide |
| **Credential Exposure** | Chaves de API, tokens, secrets aparecendo em logs, responses ou memory | Fernet encryption (CIPHER-031); redact_pimi antes de logar; output sanitization |
| **Session Hijacking** | Token de sessão/autenticação roubado entre requests | JWT com RS256; kid versioning; HTTPS only; HttpOnly cookies |
| **Privilege Escalation** | guest/user contornar RBAC para acessar tools de admin | RBAC engine com check obrigatório; admin bypass apenas com validação explícita; fail-closed |
| **MCP Gateway Attack** | Injeção via gateway MCP externo sem validação | OAuth 2.0 Resource Server; scopes validation; dynamic tool discovery; header authorization |

## Decisões de Segurança (Princípios Orientadores)

1. **Fail-closed por padrão** - Toda decisão desconhecida, erro ou edge case = deny/block
   - Tool desconhecida → deny (Anderson fail-closed, CIPHER-022)
   - Risk level UNKNOWN → deny
   - RBAC error → deny (não bypass)
   - Redis indisponível → deny (rate limiter fail-closed)
   - Qualquer exceção não prevista → deny/log/raise

2. **Princípio do Menor Privilégio** - Papel mínimo necessário para a operação
   - guest: apenas tools LOW risk, leitura apenas
   - user: tools LOW/MEDIUM de sua propriedade
   - admin: tudo (com HITL para HIGH/CRITICAL)

3. **Defesa em Profundidade** - Múltiplas camadas de segurança
   - Layer 1: Content guard (sanitização de entrada/saída)
   - Layer 2: RBAC check (controle de papel)
   - Layer 3: Rate limiting (proteção de abuso)
   - Layer 4: Policy Engine (avaliação de risco)
   - Layer 5: HITL (aprovação humana para risco alto)
   - Layer 6: Audit logging (rastreabilidade completa)

4. **Nunca confie em input externo** - Todo conteúdo de usuário, tool output, MCP messages
   - Sanitize antes de passar ao LLM
   - Validate antes de executar
   - Sanitize antes de logar
   - Mask credentials antes de qualquer transmissão

5. **Audit tudo** - Toda decisão, erro, aprovação deve ser logada estruturadamente
   - thread_id correlato
   - tool_name, risk_level, decision, actor_role
   - timestamps para forensics
   - Integração com Prometheus metrics

## Matriz de Risco por Tipo de Ferramenta

| Ferramenta | Risk Level | Required Role | HITL Necessária |
|------------|------------|---------------|-----------------|
| web_search | LOW | GUEST | Não |
| notes_read | LOW | GUEST | Não |
| notes_write | MEDIUM | USER | Opcional (dependendo de dados) |
| calendar | MEDIUM | USER | Opcional |
| drive | MEDIUM | USER | Opcional |
| email_send | HIGH | ADMIN | Sim (obrigatória) |
| send_message | HIGH | ADMIN | Sim (obrigatória) |
| stt_transcribe | LOW | GUEST | Não |
| tts_synthesize | LOW | GUEST | Não |

## Cenários de Ataque e Respostas

### Cenário 1: Prompt Injection via Tool Output
**Ataque:** Tool retorna texto contendo `ignore previous instructions` ou padrões de injection.
**Resposta:** Content guard bloqueia e retorna `[CONTEUDO BLOQUEADO: output de 'tool_name' contem padrao suspeito]`. Tool não é executada ou resultado é limpo antes de ir ao LLM.

### Cenário 2: Usuário Guest Tenta Acessar email_send
**Ataque:** Usuário com role=guest tenta chamar ferramenta email_send.
**Resposta:** RBAC engine nega (`deny`); policy engine registra `decision=deny_rbac`; audit log criado; user recebe PermissionError com mensagem apropriada.

### Cenário 3: Admin Tenta Executar Ferramenta HIGH Sem HITL
**Ataque:** Admin tenta chamar tool de risco HIGH sem aprovação humana.
**Resposta:** Policy engine detecta HIGH + autonomous + não-admin → deny com reason "HIGH risk requires HITL". Admin deve passar por HITL flow ou desativar modo autonomous.

### Cenário 4: Vazamento de Credencial via LLM Response
**Ataque:** LLM responde com chave API exposta (ex.: `sk-....`).
**Resposta:** Content guard detecta pattern `sk-[a-zA-Z0-9]{20,}` e mascara para `[REDACTED]` ou criptografa via Fernet antes de retornar ao usuário ou logar.

### Cenário 5: MCP Gateway Sem OAuth
**Ataque:** Chamada MCP sem token de autorização ou com token inválido.
**Resposta:** Gateway rejeita com 401/403; policy engine não carrega ferramenta; user recebe erro de auth. OAuth 2.0 Resource Server valida scopes e resource identification.

## Referências

- **Security Engineering - Ross Anderson (3ª ed.)**: Capítulo 4 (Threat Modeling), Capítulo 8 (PII Handling)
- **CIPHER-032**: Prompt Injection via Tool Output
- **CIPHER-033**: HITL risk category decision matrix
- **CIPHER-031**: Fernet-based encryption for secrets
- **Axiom #1**: Fail-Closed
- **Axiom #5**: Least Privilege
- **Axiom #6**: Observability (log everything)

## Próximos Passos após Esta Documentação

1. Aplicar sanitization FIRST no pipeline agent._invoke (Diff 2)
2. Implementar Fernet PII masking no content_guard (Diff 3)
3. Fortalecer RBAC com fallbacks fail-closed (Diff 5)
4. Integrar HITL corretamente no agent loop (Diff 6)
5. Criar endpoint /health completo (Diff 7)
6. Validar toda a suite de testes ainda passa

---
*Documento gerado em 2026-09-15 como parte da Fase 1 de endurecimento de segurança.*
*Próxima revisão: após aplicação de todos diffs da Fase 1.*