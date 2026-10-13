# Auditoria completa — 10/10/2026

Feita só de leitura, sobre o código no GitHub (branch `fase-0-limpeza`, PR #2) e o app instalado (build de 20:09).
Nada foi apagado nem alterado por esta auditoria.

## 1. O que o Jefrey é hoje (um produto, dois legados misturados)

**Produto atual (o que o usuário instala):** app de Windows (`Jefrey-Setup.exe`), janela WebView2, servidor FastAPI local
em `127.0.0.1:8000`, banco SQLite, tela React (`ui/`), janela embutida do WhatsApp, 3 janelas de redes sociais.
Entrada: `src/jefrey/native/launcher.py` → `api/main.py`.

**Legado 1 — "Jefrey servidor" (Docker/Kubernetes, vários usuários, Postgres, Redis, Prometheus, Grafana):** a ideia
original, antes de virar app de computador. O README diz "não precisa de Docker" e o app não usa nada disso.

**Legado 2 — "Jefrey Stark/J.A.R.V.I.S. 1.6.0" (changelog, MCP, n8n, eventbus, CLI):** outra fase, também de servidor.

## 2. Números

| Item | Valor |
|---|---|
| Arquivos no Git | 736 (231 commits) |
| Módulos Python em `src/jefrey` | 289 (≈ 31 mil linhas) |
| Módulos alcançáveis a partir do app | 268 (93 %) |
| Módulos que o app nunca carrega | 21 (veja seção 4) |
| Testes do servidor | 1605 passam, 3 puladas (rodados agora) |
| Testes da interface | 259 passam |
| CI do PR #2 | todos os checks do GitHub passam; só os 3 de preview do Vercel falham (projetos Vercel antigos) |
| Vulnerabilidades de produção (npm) | 0 |

Alcançável pelo import não prova que funciona: prova só que está ligado.

## 3. O que foi testado de verdade no app instalado

| Área | Situação |
|---|---|
| Instalar, abrir, `/health`, 22 páginas | **verificado** (22/22) |
| WhatsApp: ler caixa de entrada, ler conversa, enviar | **verificado** (envio só para a conversa "PH", autorizada) |
| Chat com ferramentas (lembrete, notícias, agenda, busca) | **verificado hoje**, ver problemas abaixo |
| Google (agenda, e-mail, tarefas) | funciona; **a chave do Google que vazou segue ativa** |
| Cérebros: Groq | funciona, mas o plano grátis limita e às vezes falha |
| Cérebros: OpenRouter, OpenAI, DeepSeek | sem saldo — **fora do ar** |
| Cérebros: Gemini, 9router | **não testados**: faltam as chaves |
| Publicar no X/Facebook/Instagram | código e testes simulados; **nunca rodou numa conta real** |
| Ver a tela (`screen_look`) | testes simulados; **nunca rodou com um cérebro que enxerga** |
| Carrossel | gera imagens (testado); publicação não testada |
| Voz (falar/ouvir), atalho Ctrl+Alt+J | existe; **não revalidado nesta sessão** |
| Instalador assinado | **não existe** (Windows mostra "editor desconhecido") |

## 4. Por que o Jefrey parece "inútil" — achados do teste real de hoje

Cinco perguntas feitas ao app instalado:

1. **"O que eu tenho pra hoje?"** respondeu "Sem compromisso marcado" e **vazou o bloco interno `[Agora] ...` na resposta**.
   Ele só olhou a agenda. Não juntou lembretes, tarefas, clima, mensagens do WhatsApp nem os assuntos que você acompanha.
   Já existe `application/briefing.py` e a tela "Hoje", mas o chat não usa isso para essa pergunta.
2. **"Sugere um jantar"** abriu uma busca no navegador sem usar o resultado, inventou um contexto ("chegou em casa às 18h, sono às 23h")
   e deu uma receita comum.
3. **"Me lembra de ligar pro dentista"** funcionou (ferramenta chamada, lembrete criado) — mas a resposta é só "Feito!".
4. **"Notícias de IA"** funcionou, com emoji e saudação repetida ("E aí, Pedro!") em toda resposta.
5. **"O que você faz?"** respondeu bem.

Causas, em ordem de peso:
- **Demora:** 2 a 19 segundos por resposta. Isso mata a sensação de assistente.
- **Cérebro pequeno e gratuito** na frente da fila (os fortes estão sem saldo ou sem chave).
- **Sem visão de conjunto:** cada ferramenta responde isolada; não há um "resumo do dia" que cruze as fontes.
- **Nada proativo:** o Jefrey só fala quando perguntado.
- **Saudação e tom repetidos**, e conteúdo inventado quando a memória é fraca.
- **Aparência igual:** a cor já muda com o dia (feito hoje), o resto do visual não.

## 5. Segurança

Pontos que **já estão bons** (verificados por testes): sem `eval`/shell com texto do usuário; tokens fora de URL e log;
aprovação humana para ações de risco (envio, publicação); texto de terceiros tratado como dado; servidor só aceita acesso local
(Host/Origin); 0 vulnerabilidades de produção nas dependências do app; Trivy limpo.

**Riscos abertos, do mais grave ao menos:**
1. **Chave OAuth do Google vazada no chat e no histórico do Git** — ainda ativa. Revogar.
2. **Chaves de API em arquivo local**, não no cofre do Windows (Credential Manager).
3. **Instalador e atualizações sem assinatura de código** — qualquer um pode se passar pelo instalador.
4. **Contas pessoais automatizadas (WhatsApp e redes)** — risco de banimento; aceito por você.
5. **Falta teste automático de injeção de prompt** contra as ferramentas (mensagem do WhatsApp tentando mandar o Jefrey agir).
6. **Sem registro de auditoria legível** pelo usuário ("o que o Jefrey fez por mim hoje").
7. **Bandit e mypy só informativos** no CI; sem revisão de segurança independente.
8. Termos de uso e política de privacidade (`src/jefrey/legal/termos.md` e `privacidade.md`) são **rascunhos sem revisão jurídica**.

## 6. Bagunça e código morto

**Código que o app não carrega (21 módulos):**
- `cli/` (599 linhas) — linha de comando do Jefrey servidor.
- `mcp/` (server, client, n8n_bridge: ≈ 1700 linhas) — servidor MCP do legado 2.
- `eventbus/publisher.py` e `subscriber.py` — barramento do legado 1.
- `adapters/outbound/doctor.py`, `telemetry.py` e os atalhos `core/doctor`, `core/telemetry`, `core/framing`, `core/persona`, `core/recall`, `core/agent_loop`, `core/tool_runtime`.
- `api/__main__.py`.

**Arquivos de infraestrutura do legado (nenhum entra no instalador):**
`docker/`, `k8s/`, `grafana/`, `prometheus/`, `n8n/`, `site/`, `Dockerfile.api`, `Dockerfile.mcp`,
`docker-compose.yml`, `docker-compose.prod.yml`, `start_jefrey.bat`, `stop_jefrey.bat`.

**Documentação:** 49 arquivos em `docs/`; `docs/historico/` (17 arquivos) e vários planos antigos descrevem o que já não existe.
O `README.md` ainda cita OpenRouter e "extensão do Chrome" como caminho principal do WhatsApp (hoje é a janela embutida).
O `CHANGELOG.md` mistura três fases e diz "WhatsApp API oficial".

**Amarras:** testes ligados ao legado: `test_p5_alerts_drill`, `test_p5_grafana_dashboards`, `test_p5_metrics_cardinality`,
`test_doctor`, `test_local_redis`; no CI, o job `compose` e todo o `ci-cd.yaml` (deploy para Kubernetes que nunca roda).
Também há adaptadores de servidor ainda ligados ao app: `pg_memory`, `pg_memory_ttl`, `redis_memory`, `local_redis`
(o app usa SQLite e Redis em memória).

## 7. Proposta de limpeza (nada foi feito ainda)

**Etapa A — sem risco para o app (um commit, fácil de desfazer pelo Git):**
apagar infraestrutura do legado (lista acima), `docs/historico/`, planos antigos, os bats antigos;
apagar os testes `test_p5_*` e o job `compose` do CI; reescrever `README.md` e `CHANGELOG.md` só com o produto atual.

**Etapa B — código (um commit por item, com a suíte completa depois de cada um):**
remover `cli/`, `mcp/`, `eventbus/`, `doctor`, `telemetry` e os atalhos `core/*` sem uso; avaliar `pg_memory*`.
Antes, confirmar que ninguém no app chama o MCP/n8n (hoje há `docs/CONEXOES_N8N.md` e o n8n foi considerado para o WhatsApp).

**Etapa C — o que realmente muda a experiência (a ordem que eu seguiria):**
1. Corrigir o vazamento do `[Agora]` e criar o **resumo do dia** de verdade (agenda + lembretes + tarefas + clima + WhatsApp + assuntos).
2. Reduzir a demora (ordem de cérebros por velocidade; resposta parcial imediata).
3. Você coloca as chaves do Gemini e do 9router; eu valido os dois no app real.
4. Segurança: cofre do Windows, registro de auditoria, teste de injeção de prompt, revogar a chave do Google.
5. Validar de verdade publicação nas redes e visão de tela com contas suas.
6. Só depois: voz em tempo real, proatividade, controle remoto pelo celular.
7. Assinatura de código, revisão jurídica e piloto com poucas pessoas.
