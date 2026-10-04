# Plano do Produto Completo — Jefrey

Sem datas. Cada fase termina por **critério de saída verificável**, não por calendário.
Uma fase só começa quando a anterior cumpriu o seu critério.

Base: diagnóstico feito rodando o produto + comparação com 7 referências
(`C:\Users\Pedro\jarvis-references\COMPARACAO_JEFREY.md`).

## Meta

Um assistente pessoal que: conversa por texto e voz com fluidez, lembra de você,
usa ferramentas reais (arquivos, web, agenda, e-mail, tela, código), age sozinho quando
faz sentido, **pede aprovação antes de ações de risco**, e instala sem esforço.
"Melhor que as referências" significa **medido** (evals), não declarado.

## Princípios

1. **Honestidade**: nenhum número na interface é fixo. Tudo vem de `/health` e `/metrics`.
2. **Medir antes de afirmar**: nada é "pronto" sem teste/eval que passe.
3. **Segurança é o diferencial**: HITL, auditoria, assinatura, RBAC e isolamento permanecem. Toda ferramenta nova nasce com política de risco.
4. **Um fluxo por vez**: terminar o caminho principal (conversar) antes de ampliar.
5. **Sem lixo no repositório**: sem `.bak`, scripts soltos na raiz ou `.md` de status.

## Estado atual (ponto de partida)

Funciona: 9 containers saudáveis, `/chat` responde via Ollama (`qwen2.5:0.5b`), build do frontend passa, API sobe.
Quebrado/fraco:
- UI com status falso (`7/7 healthy`, `p95 52ms`, `175/175` fixos), layout sobreposto, 8 abas duplicadas, chat enterrado em jargão.
- 3 testes falham (dependem de scripts apagados); 96 arquivos apagados e não commitados; lixo na raiz.
- `evals/` apagada; só 14 arquivos de teste.
- Voz sem wake word local (`wake_word/` vazia), sem VAD/interrupção.
- 8 skills; sem arquivos, navegador, shell, tela, clima.
- Só web e CLI como canais. Modelo padrão fraco. Instalação exige Docker com 9 containers.

---

## FASE 0 — Base limpa e confiável (INÍCIO)

Objetivo: o repositório e os testes dizem a verdade.

- 0.1 Decidir o destino dos 96 arquivos apagados: restaurar o necessário ou remover os testes que dependem deles. Commitar o resultado.
- 0.2 Remover lixo da raiz (`$null`, `-p`, `:memory:.ses`, `.bak`, `test2.py`, `signing_rotate.py` se obsoleto, `tmp/`, `tmp_archive/`) e o `.venv` de `docs/cipher-audit`.
- 0.3 Consolidar documentação: manter `README`, `CHANGELOG`, `docs/REFERENCES.md`, ADRs, runbooks. Arquivar os planos/relatórios antigos em `docs/archive/`.
- 0.4 Criar o primeiro conjunto de **evals** (ver Fase 1) como esqueleto vazio, mas rodável.
- 0.5 CI que roda: testes, `ruff`, `mypy`, `tsc`, build do frontend. Fixar Python 3.12.
- 0.6 Corrigir o ambiente: pytest com pasta temporária gravável; `.env.example` completo e comentado.

**Saída:** `pytest` 100% verde; CI verde; `git status` limpo; raiz com ≤ 15 itens.

---

## FASE 1 — Medição (evals) e núcleo do chat

Objetivo: poder provar qualidade; chat principal sólido.

- 1.1 Pasta `evals/` com casos de comportamento (modelo isair/OpenJarvis): responder certo, usar a ferramenta certa, recusar ação perigosa, pedir aprovação, não vazar dado de outro usuário, lembrar fato dado antes, lidar com instrução maliciosa em conteúdo externo.
- 1.2 Métricas por eval: acerto, latência (p50/p95), custo, taxa de aprovação indevida. Relatório gerado a cada execução.
- 1.3 Chat com **streaming** (`/chat/stream`), estados de carregando/erro claros, retomada após queda, histórico persistente por thread.
- 1.4 Resposta síncrona opcional para o caso simples (hoje `/chat` devolve só `running`).
- 1.5 **Modelo configurável**: Ollama local (com orçamento de RAM exibido, como o isair) ou nuvem (Claude/OpenAI) escolhido em Configurações; padrão sensato em vez de `qwen2.5:0.5b`.
- 1.6 Tratamento de falha do LLM (timeout, falta de memória) com mensagem humana, nunca tela vazia.

**Saída:** suíte de evals roda em um comando; chat passa ≥ 90% dos casos básicos; primeira resposta visível em ≤ 2 s no modelo escolhido; nenhum erro 5xx no fluxo principal.

---

## FASE 2 — Interface nova (honesta e bonita)

Objetivo: o usuário entende e gosta de usar em 1 minuto.

- 2.1 Reduzir para 4 áreas: **Chat**, **Memória**, **Skills**, **Configurações**. Detalhes técnicos em **Avançado** (observabilidade, aprovações, conexões).
- 2.2 Chat em primeiro plano, ocupando a tela; histórico lateral; anexos; botão de voz; markdown e código com cópia.
- 2.3 Remover todo texto fixo de status; ligar a `/health` e `/metrics`; estado real "offline/degradado/ok" por componente.
- 2.4 Painel de **Aprovações** como notificação inline no chat (aprovar/negar sem trocar de tela), com explicação em português do risco.
- 2.5 Design system único (tokens, tema claro/escuro, acessibilidade AA, mobile). O HUD/reator vira elemento opcional, não o centro. Remover componentes duplicados (Chat/ChatStudio, Memory/MemoryStudio, Knowledge/Skills).
- 2.6 Onboarding curto (3 passos: modelo, voz opcional, conexões), sem jargão, sem tour que cubra a tela.
- 2.7 PWA instalável e funcionando offline para a casca da interface.

**Saída:** teste end-to-end (Playwright) cobre abrir, conversar, aprovar, trocar modelo, em desktop e celular; Lighthouse ≥ 90 (desempenho, acessibilidade, PWA); nenhuma string de status fixa no código (verificado por teste).

---

## FASE 3 — Ferramentas e skills (capacidade)

Objetivo: fazer coisas úteis de verdade, com segurança.

Cada ferramenta entra com: schema, nível de risco (LOW/MED/HIGH), política de aprovação, auditoria, eval próprio, limite de taxa.

- 3.1 Núcleo: arquivos (ler/escrever em pastas permitidas), busca web e leitura de página, clima, hora, calculadora, notas, lembretes.
- 3.2 Conhecimento: ler PDF/Word/Excel (MarkItDown), indexar pastas escolhidas, busca semântica com citação da fonte.
- 3.3 Google: Gmail, Agenda, Drive, Tarefas (já existe base; completar OAuth e testes reais).
- 3.4 Navegador controlado (browser-use ou equivalente) em sandbox, sempre com aprovação para ações de escrita.
- 3.5 Código e shell em **sandbox** (container isolado), HIGH por padrão.
- 3.6 Tela e visão: captura sob demanda e descrição; webcam opcional.
- 3.7 Catálogo MCP: instalar servidores MCP oficiais (arquivos, git, busca) com tela de permissões.
- 3.8 Gerenciador de skills na UI: ativar/desativar, ver permissões, ver logs de uso.
- 3.9 Casa e dispositivos (Home Assistant) como skill opcional.

**Saída:** ≥ 20 ferramentas com eval verde; nenhuma ferramenta HIGH executa sem aprovação (teste de regressão); ataque de injeção via conteúdo externo bloqueado em todos os evals de segurança.

---

## FASE 4 — Voz de verdade

Objetivo: conversar falando, sem atrito.

- 4.1 Palavra de ativação local ("Jarvis"/"Jefrey"), preenchendo `wake_word/` (openWakeWord ou equivalente), com tolerância a variações e detecção de eco.
- 4.2 VAD (detecção de fala) + fim de fala + **interrupção** (falar por cima do Jarvis corta a resposta).
- 4.3 STT: faster-whisper local (português) com opção de nuvem.
- 4.4 TTS local de qualidade (Kokoro ou equivalente) + ElevenLabs opcional; resposta falada em frases, começando antes de terminar o texto.
- 4.5 Pipeline em tempo real (Pipecat ou LiveKit) se a medição mostrar que o atual não atinge a latência alvo.
- 4.6 Privacidade: redação de dados sensíveis antes do modelo e do diário; transcrição temporária que expira.
- 4.7 Voz no navegador e no desktop com o mesmo motor.

**Saída:** latência fala→primeira palavra falada ≤ 1,5 s (local de referência definido nos evals); interrupção funciona em ≥ 95% dos casos de teste; taxa de falso acionamento da palavra de ativação abaixo do limite fixado nos evals.

---

## FASE 5 — Memória que aprende

Objetivo: lembrar o que importa, esquecer o resto, e provar.

- 5.1 Extração automática de fatos e preferências das conversas, com confirmação para itens sensíveis.
- 5.2 Camadas: trabalho (sessão), episódica, semântica, perfil do usuário. Resumo/diário periódico.
- 5.3 Portão de recall: só injeta memória relevante no contexto (menos ruído e custo).
- 5.4 Edição pelo usuário: ver, corrigir, apagar memórias, exportar tudo; "esquecer" real (apagar também embeddings e logs ligados).
- 5.5 Isolamento por usuário testado (nenhum vazamento entre usuários nos evals).
- 5.6 Índices e desempenho validados sob carga (HNSW, `pool_pre_ping`, partição por usuário).

**Saída:** evals de memória: recupera fato dado ≥ 10 turnos antes em ≥ 90% dos casos; 0 vazamentos entre usuários; apagar uma memória a remove de todas as camadas (teste).

---

## FASE 6 — Canais e proatividade

Objetivo: o Jarvis está onde você está e age no momento certo.

- 6.1 Canal Telegram primeiro (menor esforço, maior ganho); depois WhatsApp e e-mail como canal.
- 6.2 Aprovações por canal (responder "sim/não" no próprio Telegram), com verificação de identidade.
- 6.3 Agentes proativos: resumo matinal, monitor de agenda/e-mail, lembretes inteligentes, pesquisa profunda sob demanda.
- 6.4 Agendador com limites (nunca age sozinho em ação HIGH sem aprovação), pausa global e registro visível do que ele fez sozinho.
- 6.5 Orquestração de tarefas longas com plano, execução, retentativa e relatório (padrão planner/executor/fila).

**Saída:** resumo matinal entregue no canal escolhido por 7 execuções seguidas sem intervenção; nenhuma ação autônoma HIGH sem aprovação (teste); falha de canal não perde mensagem (fila).

---

## FASE 7 — Produto instalável e operável

Objetivo: qualquer pessoa instala e mantém.

- 7.1 Instalador de um comando (Windows primeiro) que configura Ollama, modelo e serviços; modo "leve" sem Postgres/Grafana para uso pessoal (SQLite), modo "completo" com a pilha atual.
- 7.2 App desktop (bandeja, atalho global, voz, notificações) — Tauri ou Electron empacotando a UI.
- 7.3 `jefrey doctor`: diagnostica ambiente, modelo, portas, permissões e propõe correção.
- 7.4 Atualização automática com reversão.
- 7.5 Backup/restauração testados (dados, memórias, configuração) e documentados.
- 7.6 Observabilidade em Avançado: painéis úteis, SLOs reais, alertas, runbooks.
- 7.7 Segurança final: revisão de ameaça atualizada, varredura de dependências, segredos fora do repositório (`.env.prod` não versionado), rotação de chaves documentada.

**Saída:** instalação limpa em máquina nova em ≤ 10 min sem editar arquivo; restauração de backup testada; `doctor` resolve ≥ 90% dos erros de ambiente do roteiro de testes.

---

## FASE 8 — Lançamento e melhoria contínua (FIM)

Objetivo: provar a superioridade e manter.

- 8.1 **Benchmark público** Jefrey × isair × OpenJarvis nos mesmos cenários (instalação, latência de voz, acerto de ferramentas, segurança, memória), com método e resultados reproduzíveis.
- 8.2 Auditoria de segurança independente do conjunto final; correção dos achados HIGH.
- 8.3 Documentação para usuário (guia leigo, vídeos curtos) e para quem contribui (arquitetura, como criar skill).
- 8.4 Versionamento semântico, notas de versão, política de suporte.
- 8.5 Ciclo contínuo: nova ferramenta → eval primeiro; regressão em eval bloqueia a entrega.

**Saída (produto completo):** todos os critérios das fases 0–7 verdes no CI; benchmark publicado mostrando vantagem nos quesitos declarados; zero achados HIGH abertos.

---

## Quadro "melhor que as referências"

| Quesito | Referência líder | Como superamos | Fase |
|---|---|---|---|
| Segurança/aprovação | OpenJarvis (parcial) | HITL + auditoria + assinatura + RBAC mantidos e testados | 3, 6, 8 |
| Ferramentas | OpenJarvis (~45) | ≥ 20 de alto valor, todas com política e eval | 3 |
| Voz | isair / Companion | Latência medida + interrupção + privacidade | 4 |
| Memória | isair (grafo) | Aprende sozinha, editável, isolada, provada | 5 |
| Canais | OpenJarvis (30+) | Poucos canais, com aprovação por canal | 6 |
| Qualidade medida | isair/OpenJarvis (evals) | Evals desde a Fase 1, bloqueiam regressão | 1, 8 |
| Interface | isair (Qt) | UI simples, honesta, PWA + desktop | 2, 7 |
| Instalação | OpenJarvis (1 comando) | 1 comando + modo leve + `doctor` | 7 |

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Escopo grande demais | Fases com saída mensurável; não abrir fase seguinte antes |
| Modelo local fraco/RAM insuficiente | Modelo configurável, orçamento de RAM, opção nuvem |
| Ferramentas poderosas = superfície de ataque | Sandbox, política de risco por ferramenta, evals de injeção |
| Copiar código com licença incompatível | Verificar `LICENSE` antes; preferir reimplementar a partir do conceito |
| Voz depende de hardware/áudio do usuário | Alvos definidos por ambiente de referência; fallback de texto sempre |
| Documentação inflada (histórico do repo) | Regra: sem `.md` de status; só README/CHANGELOG/ADRs |

## Decisões do dono do produto (fechadas)

1. **Modelo**: local por padrão (Ollama), com conexão opcional a agentes em nuvem (Claude, ChatGPT/OpenAI e outros) escolhida em Configurações. Camada de provedores intercambiável; a nuvem nunca é obrigatória.
2. **Plataforma**: Windows, aplicativo desktop (bandeja, atalho global, voz). PWA fica como acesso secundário.
3. **Canais**: todos os canais, **WhatsApp com prioridade** (Telegram e e-mail em seguida). Fase 6 passa a começar por WhatsApp.
4. **Arquivos antigos**: apagar definitivamente tudo que é obsoleto e pesa no projeto (scripts de sondagem, relatórios, `.venv` de docs, planos de status). Não apagar código não versionado (`k8s/`, `grafana/`, `monitoring/`, `prometheus/`, `gitops/`, `docker/*`, `plugins/`, `vision/`, `memory_layers.py`), que precisa ser commitado.
5. **Perfil**: uso pessoal. Modo leve (SQLite, sem Postgres/Grafana) é o padrão; multiusuário fica como modo completo opcional.
6. **Interface**: estilo Homem de Ferro / cérebro 3D, totalmente customizável (ver Fase 2, itens 2.8 a 2.10).

### Impacto das decisões nas fases

- **Fase 1.5**: provedores de modelo plugáveis (Ollama, Anthropic, OpenAI, compatível-OpenAI). Chave de nuvem guardada no cofre do Windows, nunca no repositório.
- **Fase 2.8**: núcleo visual 3D (Three.js / React Three Fiber): "cérebro" de neurônios e sinapses que reage ao estado (ouvindo, pensando, falando, ferramenta em uso, aprovação pendente) e às memórias (cada memória é um nó).
- **Fase 2.9**: HUD estilo Homem de Ferro: reator, anéis, painéis flutuantes, modo tela cheia.
- **Fase 2.10**: customização total: temas e cores, formas (cérebro, reator, orbe), intensidade, partículas, sons, layout dos painéis arrastáveis; perfis salvos e exportáveis. Modo "simples" para aparelhos fracos e acessibilidade (reduzir movimento, WebGL desligado).
  **Saída:** 60 fps em máquina de referência com GPU integrada; modo simples ≥ 30 fps sem WebGL; trocar tema/forma sem recarregar; o chat continua utilizável com a visualização desligada.
- **Fase 6**: WhatsApp primeiro (via API oficial Cloud ou ponte local, a decidir pela política de contas); verificação de identidade do remetente obrigatória antes de aprovar ações.
- **Fase 7**: empacotamento Windows (instalador + app desktop); modo leve como padrão.

---

## Estado real (atualizado)

Legenda: **feito** = implementado e verificado (testes/evals/uso no navegador) · **parcial** = existe, com limite
declarado · **não feito** = ainda não começou.

| Fase | Item | Estado | Observação |
|---|---|---|---|
| 0 | Base limpa, CI, testes verdes | feito | CI enxuto; árvore limpa; hook de pré-commit corrigido |
| 1 | Evals em um comando | feito | 34 casos contra o sistema vivo |
| 1 | Modelo configurável, local por padrão | feito | Ollama/Claude/ChatGPT/compatível; chave nunca volta ao navegador |
| 1 | Primeira palavra em ≤ 2 s | parcial | ~1,2 s em pergunta curta; sobe com contexto e com pouca RAM livre |
| 2 | Interface nova (4 áreas), status real | feito | sem números inventados; responsiva; acessível |
| 2 | Cérebro 3D personalizável | feito | 3 formas, cor, brilho, neurônios, animação; testado só neste notebook |
| 2 | Teste end-to-end com Playwright | **não feito** | validação foi por vitest (96) e uso no navegador do painel |
| 2 | Onboarding guiado | não feito | removido o tour antigo (tinha texto falso) |
| 3 | Catálogo de risco + aprovação humana | feito | 40 ferramentas, 8 de alto risco; verificado com Postgres real |
| 3 | Notas, hora, conta, clima, arquivos | feito | calculadora sem `eval`; arquivos isolados por usuário |
| 3 | Importar documentos | parcial | txt/md/csv/json/html; **PDF e Word não** |
| 3 | Google (agenda, e-mail, Drive) | parcial | código existe; **não validado com conta Google real** |
| 3 | Navegador, código/shell em sandbox, tela, MCP, Home Assistant | **não feito** | |
| 3 | Ligar/desligar skills | feito | |
| 4 | Ouvir (Whisper local), falar, interromper, conversa contínua | feito | validado com áudio real no servidor; fala só com vozes do Windows |
| 4 | Palavra de ativação local, TTS neural, tempo real (Pipecat) | **não feito** | |
| 5 | Memória multilíngue, migração, esquecer, isolamento | feito | embedding escolhido por benchmark (97% top-1) |
| 5 | Aprender fatos sozinho / grafo | **não feito** | |
| 6 | WhatsApp (API oficial) | parcial | código e testes completos; **sem teste com conta real** (veja docs/WHATSAPP.md) |
| 6 | Telegram, e-mail como canal, agentes proativos | **não feito** | |
| 7 | `doctor`, backup/restore, modo leve, iniciador, PWA | feito | service worker testado por unidade; **registro não confirmado no navegador do painel** |
| 7 | Modo sem Docker (SQLite), app nativo (bandeja/atalho), auto-atualização, instalador assinado | **não feito** | hoje exige Docker Desktop |
| 8 | README, comparação honesta, documentação | feito | veja COMPARACAO_REFERENCIAS.md |
| 8 | Benchmark público contra isair/OpenJarvis, auditoria de segurança independente | **não feito** | não executei os projetos de referência |

### Limites do ambiente que afetaram a validação

- Notebook com 16 GB, sem GPU, e Docker ocupando ~6 GB: com pouca RAM livre as respostas ficam 5 a 10 vezes mais lentas.
- O disco C: chegou a 0,5 GB livres e travou o Docker uma vez (resolvido limpando cache de build; o espaço só volta ao
  Windows compactando o disco virtual do Docker, o que exige administrador).
- O navegador embutido do painel não tem microfone nem registra service worker; essas duas coisas foram verificadas
  por outros meios (áudio sintético no servidor e testes de unidade), não ao vivo no Edge/Chrome.
