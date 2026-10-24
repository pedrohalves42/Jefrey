# Jefrey: plano das lacunas e metas em aberto

> **Para quem executa:** use superpowers:executing-plans (tudo na mesma sessão, um commit por tarefa, suíte completa verde antes de cada commit). Os passos usam `- [ ]`.

**Meta:** fechar, em ordem, as lacunas vistas na comparação com o APEX (interface viva e ações confirmadas) e todo o resto que está aberto nos planos e documentos do projeto (`2026-10-11-jefrey-finalizacao.md`, `docs/MELHORIAS.md`, `docs/CHECKLIST_LANCAMENTO.md`, `docs/AUDITORIA_CIPHER_2026-10.md`).

**Arquitetura:** a regra de sempre. Regras puras em `domain/`, casos de uso em `application/`, mundo de fora em `adapters/outbound/`, telas em `ui/src`. Cada tarefa tem teste que falha antes de passar.

**Spec:** a conversa com o dono (14–18/10/2026) e os documentos acima.

## Restrições globais
- Voz é o canal principal e fica ligada; voz masculina (Antônio) como padrão; áudio do ambiente não chega ao chat sem o nome do Jefrey.
- Nunca colar chaves pelo usuário; nunca ler `.env`; ações de risco continuam pedindo aprovação; texto de terceiros é dado.
- Uma pessoa de 70 anos precisa entender cada texto da tela (frases curtas, sem jargão).
- Compilar o instalador só em lote (uma vez por bloco de tarefas), com `exit=0`, ≈164 MB e zero ERROR.
- A chave do Google que vazou é revogada por último, pelo dono.

## Foco de revisão (o que os testes das tarefas ainda precisam provar)
- Texto de status nunca mostra erro técnico ou nome interno de ferramenta.
- Falar um aviso enquanto pensa acontece no máximo uma vez por resposta e só quando a resposta é por voz.
- Uma ação "confirmada" nunca afirma sucesso se a releitura não achou o resultado.
- Nada novo abre a rede, grava segredo em log ou lê texto de terceiros como instrução.
- Telas continuam utilizáveis em 375 px de largura.

---

## Parte 1: a lacuna 1 (mostrar o que o Jefrey está fazendo)

### Tarefa 1: Status vivo no avatar e aviso falado de espera
**Arquivos:** criar `ui/src/lib/liveStatus.ts` e `ui/src/lib/__tests__/liveStatus.test.ts`; alterar `ui/src/pages/Conversa.tsx`.
**Interfaces:** `liveStatus(i: LiveInput): string | null` (pura). `SLOW_FILLER_S = 6` em `Conversa.tsx`.
- [x] Teste: sem trabalho, nada; ferramenta em andamento vira frase em português ("Procurando notícias…"); aprovação pendente tem prioridade; texto chegando vira "Escrevendo a resposta…"; espera longa é dita com honestidade, sem prometer prazo.
- [x] Implementar `liveStatus` e ligar ao `note` do avatar enquanto responde.
- [x] Aviso falado de espera: uma vez por resposta, depois de 6 s sem ferramenta nem texto, só com resposta por voz.
- [ ] **Validação:** no app instalado, perguntar notícias e ver o avatar trocar "Pensando…" por "Procurando notícias…" e depois "Escrevendo a resposta…". (Depende do build e do seu olhar.)

---

## Parte 2: tudo que está aberto nos planos (consolidado em 18/10/2026)

### Tarefa 2: Ações confirmadas

> **Status (24/10/2026):** FEITA para lembretes (criar e cancelar releem antes de afirmar). Notas ficaram de fora: a ferramenta devolve dados para o agente, não frase. ("ações verificadas")
**Arquivos:** criar `src/jefrey/domain/verify.py` e `tests/test_verify.py`; alterar `skills/reminders.py`, `skills/notes.py`.
**Interfaces:** `confirm(kind: str, expected: dict, found: dict | None) -> str` devolve a frase final ("Criado para hoje às 10:00.") ou "Não consegui confirmar que ficou salvo.".
- [ ] Teste: lembrete criado e relido com o mesmo texto e horário gera a frase com o horário; relido ausente gera o aviso de não confirmado; nunca afirma sucesso sem achar.
- [ ] Implementar a releitura depois de criar lembrete e nota, e usar `confirm` na resposta da ferramenta.
- [ ] Validação: pedir um lembrete no app e ver a frase com horário.

### Tarefa 3: Lembretes por voz

> **Status (24/10/2026):** FEITA: fala na hora, repete a cada 5 min até 3 vezes, silêncio das 22 h às 8 h, só com resposta por voz ligada. com repetição até confirmar
**Arquivos:** `src/jefrey/application/` (repetição), `ui/src/hooks/useReminders.ts`.
- [ ] Teste: lembrete vencido não confirmado repete a cada 5 min, no máximo 3 vezes; "ok" para.
- [ ] Implementar a repetição falada; respeitar o horário de silêncio (22 h às 8 h).
- [ ] Validação: lembrete de 1 minuto no app instalado.

### Tarefa 4: Isolar o áudio

> **Status (24/10/2026):** FEITA (portão antes do Whisper: descarta trecho fraco ou longo fora da conversa). Limite honesto: sem motor de palavra de chamada dedicado, voz alta perto do microfone ainda é transcrita e depois filtrada pelo nome. do ambiente antes de transcrever
**Arquivos:** `ui/src/lib/voiceGate.ts`, `src/jefrey/api/stt.py`, `src/jefrey/core/wake.py`.
- [ ] Teste: trecho sem o nome do Jefrey fora da janela de conversa é descartado sem chegar à transcrição completa (portão por energia e palavra de chamada).
- [ ] Teste: com o nome dito, o trecho passa; a janela de 25 s continua valendo.
- [ ] Validação: com TV ligada ao fundo por 2 min, nada aparece no chat.

### Tarefa 5: Notícias

> **Status (24/10/2026):** FEITA de outro jeito: a busca já levava 0,5 a 2 s; o tempo era das rodadas do modelo. Pedido de notícias agora responde direto da busca (sem modelo). dentro de 15 s de forma estável
**Arquivos:** `skills/web_search.py`, `domain/` (cache), testes em `tests/test_news_cache.py`.
- [ ] Teste: mesma busca em 10 min reaproveita o resultado; busca de várias fontes roda em paralelo com teto de 8 s por fonte.
- [ ] Validação: cinco perguntas de notícia no app, todas ≤ 15 s.

### Tarefa 6: Ordem dos cérebros

> **Status (24/10/2026):** FEITA: Configurações > Cérebros mostra usos, falhas e tempo por cérebro. provada pelo uso
**Arquivos:** `ui/src/components/Cerebros.tsx`, `/brains/metrics`.
- [ ] Teste: com ≥ 5 chamadas por cérebro, a tela mostra tempo mediano e falhas por função.
- [ ] Validação: depois de uso real, a ordem mostrada bate com a medida.

### Tarefa 7: Primeira abertura

> **Status (24/10/2026):** JÁ EXISTIA (`primeiraVez.ts`, conduzida por voz, com testes). guiada por voz
**Arquivos:** `ui/src/pages/BemVindo.tsx`, `ui/src/lib/primeiraVez.ts`.
- [ ] Teste: o roteiro fala cada passo e avança com "sim"/"próximo" ditos; sem microfone, cai no botão.
- [ ] Validação: abrir o app com dados limpos e concluir só falando.

### Tarefa 8: Voz local

> **Status (24/10/2026):** FEITA: depois de 2 falhas da voz da nuvem e sem a local instalada, a tela oferece baixar (nunca baixa sozinha). como reserva guiada
**Arquivos:** `ui/src/components/VoiceDownload.tsx`, `src/jefrey/api/voice_routes.py`.
- [ ] Teste: quando a voz da nuvem falha duas vezes seguidas e a local não está instalada, a tela oferece baixar (60 MB) com um botão, sem baixar sozinha.
- [ ] Validação: simular falha da nuvem e ver a oferta.

### Tarefa 9: Acessibilidade

> **Status (24/10/2026):** FEITA: letra normal/grande/enorme e alto contraste (axe sem violações). Falta o Narrador do Windows, só com você.
**Arquivos:** `ui/src/index.css`, `ui/src/lib/appearance.tsx`, `ui/src/__tests__/a11y.test.tsx`.
- [ ] Teste: opção "letra grande" aumenta legendas e botões; modo alto contraste atinge razão 7:1 nos textos principais; todo botão tem nome para leitor de tela.
- [ ] Validação: conferir com o leitor de tela do Windows (Narrador) a tela Conversa.

### Tarefa 10: Painel de topo

> **Status (24/10/2026):** JÁ EXISTIA (faixa do dia com tempo, compromisso e dólar, hora e atalhos por momento do dia). (relógio, clima e atalhos)
**Arquivos:** `ui/src/components/DayStrip.tsx`.
- [ ] Teste: mostra hora, clima e três atalhos do momento do dia sem passar de 375 px.
- [ ] Validação: captura em três larguras.

### Tarefa 11: Mais comandos

> **Status (24/10/2026):** JÁ EXISTIA (`close_app`, `type_text` em risco alto, `screen_look`). do computador
**Arquivos:** `skills/computer.py`, `domain/tool_catalog.py`.
- [ ] Teste: "fechar o programa X" só fecha programa da lista permitida e pede aprovação; "escrever neste programa" é risco alto; captura de tela só quando pedida.
- [ ] Validação: abrir e fechar o Bloco de Notas por voz.

### Tarefa 12: Modo família

> **Status (24/10/2026):** FEITA: consentimento, contato, oferta no domingo à noite, resumo só com contagens, envio sempre com aprovação. (resumo semanal ao cuidador)
**Arquivos:** `application/` (resumo), `api/` (consentimento).
- [ ] Teste: sem consentimento registrado nada é enviado; com consentimento sai um resumo por semana sem texto de conversas.
- [ ] Validação: consentimento e envio de teste para um contato escolhido pelo dono.

### Tarefa 13: Telemetria

> **Status (24/10/2026):** ADIADA: não há servidor de destino. Decisão do dono: sem ele, coletar não faz sentido. sem dados pessoais (opcional)
- [ ] Teste: desligada por padrão; ligada, só conta eventos (tela aberta, erro por categoria), nunca texto, nome ou chave.
- [ ] Validação: inspecionar o que seria enviado antes de ligar.

### Tarefa 14: Qualidade e peso

> **Status (24/10/2026):** FEITA: `scripts/e2e_installed.py`, código sem uso = 0 módulos, instalador sem as APIs do Google não usadas (~100 MB), documentos atualizados. Whisper opcional não foi feito (60 MB do ctranslate2 é a voz do dono: manter).
- [ ] Script único `scripts/e2e_installed.py` que roda `verify_installed`, `audit_whatsapp`, `check_connectivity` e o probe de perguntas, com relatório.
- [ ] Instalador menor: `faster-whisper`/`ctranslate2` como download opcional (medir antes e depois; meta: menos de 130 MB).
- [ ] P-07: rodar `scripts/dead_code.py` e remover o que continuar sem uso (visão só se não for carregada).
- [ ] Atualizar `docs/CHECKLIST_LANCAMENTO.md`, `docs/MELHORIAS.md` e `docs/PLANO_EXECUCAO_SESSOES.md` com o estado real.

### Tarefa 15: Fechamento
- [ ] Um build, uma instalação e a bateria completa no app instalado; atualizar o PR #2 e o CHANGELOG.

---

## Fora do código (só o dono consegue; ficam registrados, não bloqueiam as tarefas acima)
1. Parear um celular de verdade (celular por QR) e olhar os avatares Robô e Escudo na tela.
2. Chave Gemini com acesso ao Live (voz em tempo real) e entrar no X, Facebook e Instagram para validar a publicação.
3. Certificado de assinatura do instalador, revisão jurídica dos textos, endereço do manifesto de atualização, extensão na Chrome Web Store, verificação do app no Google, licença/cobrança/domínio.
4. Piloto com 3 a 5 pessoas (uma de 70 anos) e bateria de 17 perguntas com chave de nuvem real.
5. Desligar os 3 checks do Vercel de projetos antigos e renovar o `GITHUB_TOKEN` inválido do ambiente.
6. **Por último:** revogar a chave do Google que vazou no chat.
