# Jefrey 100% — Plano de Fechamento (do início ao fim)

> **Para quem for executar:** USE `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans`. Os passos usam caixas `- [ ]`. Tarefas marcadas **[VOCÊ]** dependem de contas, documentos ou pessoas que só o dono do produto tem: o executor prepara tudo e para ali.

**Objetivo:** levar o Jefrey de ~80% construído / ~55% provado para "pode vender": uma pessoa de 70 anos instala, configura e usa sozinha, por voz, com o HUD estilo Jarvis do vídeo de referência.

**Arquitetura:** não muda. FastAPI + SQLite/Chroma embutidos, UI React servida pelo próprio app, instalador PyInstaller + Inno Setup. Cada lacuna vira um módulo pequeno em `src/jefrey/core/`, com rota fina em `src/jefrey/api/`, ferramenta em `src/jefrey/skills/` e entrada em `tool_catalog.py`. Tudo com teste hermético; o que exige conta ou pessoa real vira **portão de aceite** (seção "Portões") com roteiro escrito.

**Tecnologias:** Python 3.12 (`C:\Users\Pedro\jv312`), FastAPI, httpx, pytest; React/Vite/Tailwind, vitest; PyInstaller, Inno Setup; Ed25519 (atualização); Windows (ctypes/UIAutomation).

**Spec:** `CLAUDE.md` (regras de trabalho), `docs/COMO_O_JEFREY_FUNCIONA.md`, `docs/CHECKLIST_LANCAMENTO.md`, `docs/MELHORIAS.md`, critérios do usuário nesta conversa (seção "Critérios" abaixo).

## Critérios (a régua dos 100%)
| # | Critério (dito pelo usuário) | Medida de "100%" |
|---|---|---|
| C1 | Idoso de 70 anos instala, configura e usa sozinho | Portão P1: 4 de 5 pessoas concluem instalação + primeira conversa por voz sem ajuda |
| C2 | Voz é o caminho principal; Jefrey fala natural, não "robótico/de IA" | Portão P2: nota ≥ 4/5 de naturalidade em 5 ouvintes; fala começa em ≤ 1,5 s |
| C3 | Visual de painel Jarvis (vídeo), cérebro/avatar predominante e **pulsa ao falar** | Portão P3: pulso acompanha o volume real da voz; 60 fps em PC médio |
| C4 | Controlar o computador por voz, inclusive outros programas | Portão P4: 10 comandos reais (abrir, fechar, digitar, atalhos, Blender) executados |
| C5 | Conexões em abas, 1 clique onde possível; nuvem como padrão, local só em máquina forte | Portão P5: OpenRouter 1 clique; demais "colar e conectar"; Google 1 clique com cliente Desktop |
| C6 | Alexa, WhatsApp (só pelo navegador), Google funcionando | Portão P6: cada integração testada com conta real |
| C7 | Aprender sozinho + por pedido + fontes/links, teto US$0,10/dia | Teste de teto + 3 dias de uso real |
| C8 | Atualização automática e instalador assinado | Portão P7: atualização 0.9.x→1.0.0 em PC limpo; sem aviso de "editor desconhecido" |
| C9 | Projeto limpo e pronto para entregar (`Jefrey-Pronto`) | Script `scripts/pack_pronto.py` reproduz a pasta; sem segredos |
| C10 | Segurança e privacidade (LGPD) | pip-audit limpo ou risco aceito; textos jurídicos preenchidos e revisados |

## Restrições globais (valem em toda tarefa)
- Nunca gerar código com barras invertidas por heredoc no Bash: usar Write/Edit; scripts de patch com `assert antigo in texto`.
- Python do projeto: `C:\Users\Pedro\jv312\Scripts\python.exe` (3.12). Caminhos curtos. Comandos longos em segundo plano com log.
- Testes: `C:\Users\Pedro\jv312\Scripts\python.exe -m pytest tests -q --ignore=tests/e2e --ignore=tests/smoke --basetemp=C:/Users/Pedro/jt -p no:warnings`; UI: `cd ui && npx tsc --noEmit -p . && npx vitest run`. Todos passam antes de cada commit. Nunca `ruff --fix` em massa.
- Nunca ler `.env`; segredos só em cofre (`secret_store`), nunca em URL, log ou resposta. Texto de terceiros é dado, nunca instrução.
- Tom informal, pelo nome; textos de tela em português simples, letra grande no Modo Fácil.
- Ferramentas de risco (`high`) sempre pedem aprovação; mudou autenticação/CORS/ferramentas de risco: rodar `tests/test_local_guard.py`, `tests/test_google_oauth_state.py` e os testes de aprovação.
- Um servidor de teste por vez (porta 8000); dados em `C:\Users\Pedro\jefrey_home_*`; encerrar o anterior.
- Rate limit por usuário 60/min; rotas leves entram em `_USER_RL_EXEMPT`.
- Alterou a interface: `cd ui && npm run build:api` antes de gerar o instalador.

## Review Focus (o que os testes das tarefas não cobririam sozinhos)
1. **Sem internet / serviço fora do ar:** voz da nuvem, atualização, cérebros e Alexa devem falhar com frase simples e cair para o caminho local, nunca travar a conversa.
2. **Dois Jefreys / porta 8000 ocupada:** o segundo abre o primeiro ou avisa em português; nunca fica mudo (já causou `redirect_uri_mismatch`).
3. **Texto de terceiros mandando agir** (e-mail, site, WhatsApp: "abra X", "digite Y"): nunca vira ferramenta de controle do computador.
4. **Digitar/clicar na janela errada:** a ação só roda com a janela confirmada em foco e com aprovação; o botão de parada interrompe na hora.
5. **Reinstalar/atualizar preserva dados e a extensão** (pasta em Documentos), e a desinstalação não apaga memórias sem perguntar.

---

## Mapa de fases e dependências
```
FASE A  Régua e automação de verificação   (T1–T3)   ← base de todas
FASE B  Voz natural e HUD vivo             (T4–T7)   ← C2, C3
FASE C  Controle do computador por dentro  (T8–T11)  ← C4
FASE D  Idoso: primeira vez, acessibilidade (T12–T15) ← C1
FASE E  Integrações reais                  (T16–T20) ← C5, C6, C7
FASE F  Distribuição e comercial           (T21–T26) ← C8, C9, C10
FASE G  Piloto e fechamento                (T27–T29) ← todos
```
Ordem: A → (B, C, D em paralelo, se houver mais de um executor) → E → F → G. Cada tarefa termina com commit em `fase-0-limpeza` (ou branch própria) e suíte verde.

## Estrutura de arquivos (decisões travadas)
| Arquivo | Responsabilidade |
|---|---|
| `scripts/verify_installed.py` (novo) | Roda no `.exe` instalado: as 13+ verificações de aceite, saída `OK/FALHOU` por item |
| `docs/PORTOES.md` (novo) | Roteiro de cada portão P1–P7 com passos, quem faz e como registrar |
| `src/jefrey/core/localvoice.py` (novo) | Voz local neural (Piper): baixar modelo, sintetizar, escolher voz |
| `src/jefrey/api/voice_routes.py` (novo) | `GET /voice/engines`, `POST /voice/speak` (local ou nuvem), unifica `cloudvoice_routes.py` |
| `ui/src/lib/voiceLevel.ts` (novo) | Nível de áudio real (WebAudio `AnalyserNode`) para o pulso |
| `src/jefrey/core/uiautomation.py` (novo) | Janela em foco, digitar texto, atalhos permitidos (Windows, sem shell) |
| `src/jefrey/skills/computer_ui.py` (novo) | Ferramentas `focus_window`, `type_text`, `press_hotkey`; todas `high` |
| `src/jefrey/core/appconnectors/` (novo) | Conectores por programa (Blender), cada um com lista fechada de comandos |
| `ui/src/pages/PrimeiraVez.tsx` (novo) | Assistente de primeira abertura guiado por voz |
| `src/jefrey/core/support.py` + `api/support_routes.py` (novos) | "Algo deu errado": relatório sem segredos para suporte |
| `scripts/release.py` (novo) | Build → assina → manifesto → pasta de publicação, um comando |
| `scripts/pack_pronto.py` (novo) | Gera `Desktop\Jefrey-Pronto` de forma reproduzível |

---

# FASE A — Régua e automação de verificação

### Task 1: Verificação automática do instalado (`verify_installed.py`)
**Files:** Create `scripts/verify_installed.py`, `tests/test_verify_installed.py`.
**Interfaces:** Produces `run_checks(base_url: str, token: str) -> list[tuple[str, bool, str]]` (nome, passou, detalhe) e `main() -> int` (0 = tudo OK).
- [ ] **Step 1:** Teste `test_checks_listam_o_que_falhou` com servidor falso (`httpx.MockTransport`): `/health` 200 e `/brains` 500 → resultado contém `("brains", False, …)`; `main` devolve 1.
- [ ] **Step 2:** Rodar: `pytest tests/test_verify_installed.py -v` → FALHA (módulo não existe).
- [ ] **Step 3:** Implementar `run_checks` cobrindo: `/health`, `/legal/status`, `/brains`, `/skills` (nenhum risco `unknown`), `/connections/google`, `/voice/engines`, `/updates/check`, `/system/telemetry`, `/alexa`, `/studies/sources`, `/wa/open-extension-folder` (pasta em Documentos existe), páginas SPA com `Accept: text/html`. Token via `POST /auth/dev-token`. Sem imprimir segredos.
- [ ] **Step 4:** Teste passa; rodar contra o `.exe`: `Jefrey.exe` em home limpa (`JEFREY_HOME=C:/Users/Pedro/jefrey_home_v`) e `python scripts/verify_installed.py http://localhost:8000` → todos `OK`.
- [ ] **Step 5:** Commit `test: verificação automática do instalado`.

### Task 2: Roteiro dos portões (`docs/PORTOES.md`)
**Files:** Create `docs/PORTOES.md`.
- [ ] **Step 1:** Escrever P1–P7 com: pré-requisito, passos numerados, critério de passe/falha (números da tabela de Critérios), onde anotar o resultado (tabela no próprio arquivo, uma linha por tentativa com data e resultado).
- [ ] **Step 2:** Ligar `docs/CHECKLIST_LANCAMENTO.md` a cada portão (coluna "Portão").
- [ ] **Step 3:** Commit `docs: roteiro dos portões de aceite`.

### Task 3: Suíte de contrato dos cérebros (opt-in, chave real)
**Files:** Create `tests/contract/test_brains_real.py`; Modify `pyproject.toml` (marker `contract`).
**Interfaces:** Consumes `brains.connect(id, api_key)` e `brains.state()`.
- [ ] **Step 1:** Testes marcados `@pytest.mark.contract` que só rodam com `JEFREY_CONTRACT_KEYS` (arquivo fora do repo): para cada cérebro conectado, uma pergunta curta devolve texto; principal inválido + reserva válida ⇒ resposta vem da reserva (`test_reserva_assume_com_chave_real`).
- [ ] **Step 2:** `pytest -m "not contract"` continua sendo o padrão da suíte; com a chave, `pytest -m contract` passa. **[VOCÊ]** fornece as chaves para rodar.
- [ ] **Step 3:** Commit `test: contrato dos cérebros com chave real (opt-in)`.

---

# FASE B — Voz natural e HUD vivo (C2, C3)

### Task 4: Voz local neural (Piper) — motor
**Files:** Create `src/jefrey/core/localvoice.py`, `tests/test_localvoice.py`; Modify `requirements.txt`, `packaging/build_exe.bat` (coletar `piper` e `onnxruntime`).
**Interfaces:** Produces `available() -> bool`, `model_status() -> dict` (`{"installed": bool, "size_mb": int}`), `async download_model(progress=None) -> None`, `synth(text: str) -> bytes` (WAV), `VOICE = "pt_BR-faber-medium"`.
- [ ] **Step 1:** Testes: `test_modelo_so_instala_se_sha256_confere` (download falso com hash errado → apaga e levanta erro em português), `test_synth_sem_modelo_levanta_erro_simples`, `test_texto_longo_e_cortado`, `test_url_do_modelo_e_fixa` (endereço no código, não vem de fora).
- [ ] **Step 2:** Rodar → FALHA.
- [ ] **Step 3:** Implementar. Modelo baixado sob demanda (≈60 MB) para `%LOCALAPPDATA%\Jefrey\data\voices\`, com SHA-256 fixo no código; síntese em thread; sem shell.
- [ ] **Step 4:** Testes passam; síntese real manual: salvar WAV e ouvir. **[VOCÊ]** avalia naturalidade (Portão P2).
- [ ] **Step 5:** Commit `feat(voz): motor local neural (Piper) com download verificado`.

### Task 5: API única de fala e escolha automática
**Files:** Create `src/jefrey/api/voice_routes.py`, `tests/test_voice_routes.py`; Modify `src/jefrey/api/cloudvoice_routes.py` (reaproveita), `src/jefrey/api/main.py` (registrar).
**Interfaces:** Produces `GET /voice/engines -> {"engines": [{"id": "cloud"|"local"|"browser", "available": bool, "label": str}], "default": str}` e `POST /voice/speak {text, engine?} -> audio/mpeg|audio/wav`. Ordem padrão: `cloud` (se ChatGPT conectado) → `local` (se modelo instalado) → `browser`.
- [ ] **Step 1:** Testes: `test_padrao_prefere_nuvem_depois_local`, `test_falha_da_nuvem_cai_para_local` (409 da nuvem ⇒ resposta do local), `test_sem_login_401`, `test_texto_limitado`.
- [ ] **Step 2–4:** Implementar, rodar, passar.
- [ ] **Step 5:** Commit `feat(voz): API única com queda automática nuvem→local→navegador`.

### Task 6: UI da voz (motor, download do modelo, seletor)
**Files:** Modify `ui/src/hooks/useSpeaker.ts` (usar `/voice/speak`), `ui/src/pages/Conversa.tsx` (seletor "Voz"), `ui/src/pages/Configuracoes.tsx` (botão "Baixar voz natural", barra de progresso); Create `ui/src/lib/voice.ts` (`getEngines`, `startModelDownload`).
**Interfaces:** Consumes `GET /voice/engines`; Produces `useSpeaker()` com `engine: "cloud"|"local"|"browser"` e `setEngine`.
- [ ] **Step 1:** Testes vitest `speaker.test.ts`: `usa o motor padrao da API`, `cai para o navegador se a API falhar`, `cancel interrompe o audio e a fila`.
- [ ] **Step 2–4:** Implementar e passar; `npx tsc --noEmit -p .` limpo.
- [ ] **Step 5:** Commit `feat(voz): seletor de motor e download da voz natural na UI`.

### Task 7: Pulso pelo volume real e HUD vivo
**Files:** Create `ui/src/lib/voiceLevel.ts`; Modify `ui/src/hooks/useVoicePulse.ts`, `ui/src/pages/Conversa.tsx`, `ui/src/components/hud/JarvisHud.tsx`, `ui/src/index.css`.
**Interfaces:** Produces `createLevelMeter(audio: HTMLAudioElement): { level(): number; stop(): void }` (0–1, RMS do `AnalyserNode`); `nextPulse(prev, speaking, word, t, level?)` aceita nível real.
- [ ] **Step 1:** Testes: `nextPulse com level alto bate perto de 1`, `sem level mantém o comportamento atual (palavra/ondulação)`, `level 0 e speaking decai`.
- [ ] **Step 2–4:** Implementar: para áudio da nuvem/local usar o medidor real; para `speechSynthesis` manter palavra+ondulação. HUD: partículas reagem ao nível do microfone ao ouvir e ao nível da voz ao falar; `prefers-reduced-motion` reduz animação; teste de desempenho manual ≥ 50 fps.
- [ ] **Step 5:** Commit `feat(hud): pulso e partículas pelo volume real da voz`. **Portão P3 [VOCÊ]**.

---

# FASE C — Controle do computador por dentro (C4)

### Task 8: Núcleo de automação segura (`uiautomation.py`)
**Files:** Create `src/jefrey/core/uiautomation.py`, `tests/test_uiautomation.py`.
**Interfaces:** Produces `foreground() -> tuple[int, str, str]` (hwnd, título, programa), `focus(hwnd: int) -> bool`, `type_text(text: str) -> None` (via `SendInput` Unicode), `hotkey(combo: str) -> None` aceitando só `ALLOWED_HOTKEYS` (ex.: `ctrl+c`, `ctrl+v`, `ctrl+s`, `ctrl+z`, `alt+tab`, `enter`, `esc`, `win+d`), `PROTECTED` (reaproveita lista de `skills/computer.py`).
- [ ] **Step 1:** Testes (com `SendInput`/`user32` simulados): `test_hotkey_fora_da_lista_e_recusado`, `test_nao_digita_em_janela_protegida`, `test_texto_maior_que_500_e_recusado`, `test_nao_digita_se_a_janela_mudou` (foco diferente do confirmado), `test_texto_com_comandos_nao_e_executado` (digitar `rm -rf` é só texto).
- [ ] **Step 2–4:** Implementar sem shell nem `eval`; teste manual no Bloco de Notas.
- [ ] **Step 5:** Commit `feat(computador): núcleo de automação com lista fechada`.

### Task 9: Ferramentas `focus_window`, `type_text`, `press_hotkey`
**Files:** Create `src/jefrey/skills/computer_ui.py`, `tests/test_computer_ui_skill.py`; Modify `src/jefrey/skills/__init__.py`, `src/jefrey/core/tool_catalog.py` (as três `high`), `src/jefrey/core/agent_loop.py` (GROUPS: "digita", "escreve em", "atalho", "cola"), `src/jefrey/core/persona.py` (honestidade: o que agora consegue e o que não).
**Interfaces:** Consumes `uiautomation.*`, `computer.match_windows`; Produces ferramentas com assinatura `focus_window(name: str)`, `type_text(text: str, window: str)`, `press_hotkey(combo: str, window: str)`; a aprovação mostra título da janela e o texto a digitar.
- [ ] **Step 1:** Testes: `test_todas_as_tres_pedem_aprovacao`, `test_type_text_sem_aprovacao_nao_digita` (usa `approval_timeout`), `test_texto_vindo_de_email_nao_aciona_ferramenta` (conteúdo em `<dados>` não seleciona `type_text`), laço real do agente (`run_agent`) abre o Bloco de Notas e digita (com `uiautomation` falso).
- [ ] **Step 2–4:** Implementar e passar.
- [ ] **Step 5:** Commit `feat(computador): digitar e atalhos com aprovação`.

### Task 10: Botão de parar e registro de ações
**Files:** Modify `src/jefrey/core/tool_runtime.py` (flag global `computer_halt`), `src/jefrey/api/approvals.py`, `ui/src/pages/Conversa.tsx` (botão "Parar tudo" sempre visível durante ação), `src/jefrey/core/audit.py` (registrar ação do computador); Test `tests/test_computer_halt.py`.
- [ ] **Step 1:** Testes: `test_parar_tudo_cancela_fila_de_acoes`, `test_acao_registrada_na_auditoria_sem_o_texto_digitado` (guarda só tamanho e janela).
- [ ] **Step 2–4:** Implementar; atalho de teclado `Ctrl+Alt+J` para parar (hotkey global do Windows já existe no launcher).
- [ ] **Step 5:** Commit `feat(computador): botão e atalho de parada, auditoria`.

### Task 11: Conectores por programa (Blender como o primeiro)
**Files:** Create `src/jefrey/core/appconnectors/__init__.py`, `src/jefrey/core/appconnectors/blender.py`, `extensions/blender/jefrey_addon.py`, `tests/test_appconnectors.py`; Modify `src/jefrey/skills/computer_ui.py` (ferramenta `app_command(app: str, command: str, args: dict)`), `tool_catalog.py` (`high`).
**Interfaces:** Produces `COMMANDS = {"add_cube", "add_sphere", "move_object", "delete_object", "render"}` com validação de argumentos; transporte é um soquete local em `127.0.0.1` com token de sessão; o add-on do Blender só aceita comandos dessa lista.
- [ ] **Step 1:** Testes: `test_comando_fora_da_lista_e_recusado`, `test_argumentos_validados` (tamanho, tipo, limites), `test_so_aceita_127_0_0_1`, `test_sem_token_recusa`.
- [ ] **Step 2–4:** Implementar o conector e o add-on; **[VOCÊ]** instala o add-on no Blender e valida "crie um cubo" (Portão P4).
- [ ] **Step 5:** Commit `feat(computador): conector do Blender com lista fechada de comandos`.

---

# FASE D — Idoso: primeira vez e acessibilidade (C1)

### Task 12: Assistente de primeira vez guiado por voz
**Files:** Create `ui/src/pages/PrimeiraVez.tsx`, `ui/src/lib/primeiraVez.ts`, `ui/src/__tests__/primeira-vez.test.ts`; Modify `ui/src/App.tsx` (rota), `ui/src/lib/llm.ts` (`needsWelcome` leva ao assistente), `src/jefrey/api/auth_middleware.py` (`_SPA_PAGES`).
**Interfaces:** Produces `STEPS: {id, fala, tela}[]` (nome → termos → cérebro → voz → "experimente: diga 'que horas são'"), `nextStep(state, answer) -> state`; cada passo é falado e aceita resposta por voz ou toque.
- [ ] **Step 1:** Testes: `percorre todos os passos só com respostas de voz simuladas`, `pular um passo nunca trava o seguinte`, `fala cada passo em frases de até 20 palavras`.
- [ ] **Step 2–4:** Implementar; Modo Fácil ligado por padrão para quem passa pelo assistente.
- [ ] **Step 5:** Commit `feat(ux): assistente de primeira vez por voz`. **Portão P1 [VOCÊ]**.

### Task 13: Acessibilidade (WCAG AA, leitor de tela, teclado)
**Files:** Modify `ui/src/index.css`, componentes com `aria-*` faltando; Create `ui/src/__tests__/a11y.test.ts` (usa `jest-axe`/`vitest-axe`); Modify `ui/package.json` (dev dep).
- [ ] **Step 1:** Teste: renderizar Conversa, Conexões, Skills, Aprender e PrimeiraVez e exigir zero violações `serious/critical`; `test_tamanho_de_alvo_minimo_44px` no Modo Fácil; `test_todo_botao_tem_nome`.
- [ ] **Step 2–4:** Corrigir o que o axe apontar; contraste ≥ 4,5:1; foco visível; navegação completa por Tab.
- [ ] **Step 5:** Commit `fix(a11y): zero violações sérias e navegação por teclado`.

### Task 14: "Algo deu errado" — suporte sem expor segredos
**Files:** Create `src/jefrey/core/support.py`, `src/jefrey/api/support_routes.py`, `ui/src/components/ReportProblem.tsx`, `tests/test_support.py`; Modify `AppShell.tsx` (botão em Ajuda).
**Interfaces:** Produces `build_report() -> bytes` (zip: versão, SO, últimos 500 logs já filtrados por `logredact`, estado das conexões sem valores) e `POST /support/report -> arquivo` salvo em Documentos; nunca envia sozinho.
- [ ] **Step 1:** Testes: `test_relatorio_nao_contem_tokens_nem_chaves` (semear segredos falsos e procurar no zip), `test_relatorio_tem_versao_e_log`, `test_sem_login_401`.
- [ ] **Step 2–4:** Implementar e passar.
- [ ] **Step 5:** Commit `feat(suporte): relatório de problema sem segredos`.

### Task 15: Erros em português simples em todo o app
**Files:** Modify `src/jefrey/api/auth.py:112,158` (mensagem do OAuth sem citar `.env`), demais `HTTPException` técnicas encontradas por `grep -rn "\.env\|stack\|Traceback" src/jefrey/api`; Test `tests/test_mensagens_simples.py`.
- [ ] **Step 1:** Teste varre `detail=` de todas as rotas e falha se contiver `.env`, `JEFREY_`, `localhost` ou nome de variável.
- [ ] **Step 2–4:** Trocar por frases do tipo "Isso ainda não está liberado nesta cópia. Fale com quem te entregou o Jefrey."; passar.
- [ ] **Step 5:** Commit `fix(ux): mensagens de erro sem jargão`.

---

# FASE E — Integrações reais (C5, C6, C7)

### Task 16: Google 1 clique de verdade
**Files:** Modify `docs/GOOGLE.md`, `src/jefrey/core/google_oauth.py` (diagnóstico), `ui/src/pages/Conexoes.tsx`; Test `tests/test_google_diagnostico.py`.
**Interfaces:** Produces `diagnose(origin: str) -> {"redirect_uri": str, "client_type": "desktop"|"web"|"unknown", "port_ok": bool}`.
- [ ] **Step 1:** Testes: `test_cliente_desktop_aceita_qualquer_porta`, `test_cliente_web_exige_endereco_registrado`, `test_porta_diferente_de_8000_avisa`.
- [ ] **Step 2–4:** Implementar; a tela mostra o diagnóstico em frases simples.
- [ ] **Step 5:** Commit. **[VOCÊ]** cria o cliente "Aplicativo para computador", roda `scripts/seed_google_defaults.py`; o executor gera o instalador e roda o **Portão P5/P6**: login → "Conectado" → "o que tenho na agenda amanhã?" responde com dados reais.

### Task 17: WhatsApp real e extensão empacotada
**Files:** Create `scripts/pack_extension.py` (zip para Chrome Web Store), `tests/test_pack_extension.py`; Modify `extensions/whatsapp/manifest.json` (versão e permissões mínimas).
- [ ] **Step 1:** Testes: `test_zip_tem_manifest_e_sem_arquivos_de_teste`, `test_permissoes_minimas` (só `web.whatsapp.com` e `localhost`).
- [ ] **Step 2–4:** Implementar e passar.
- [ ] **Step 5:** Commit. **[VOCÊ]** (a) testa pareamento com WhatsApp real (Portão P6); (b) publica na Chrome Web Store (conta de desenvolvedor, US$5).

### Task 18: Alexa verificada e com plano B
**Files:** Modify `src/jefrey/core/alexa.py`, `docs/ALEXA.md` (novo), `ui/src/components/AlexaTab.tsx`; Test `tests/test_alexa.py`.
- [ ] **Step 1:** Com a resposta real do Voice Monkey (capturada no teste do **[VOCÊ]** com conta real), adicionar `test_resposta_real_do_voice_monkey` com o corpo capturado; ajustar `_call` se o formato divergir.
- [ ] **Step 2:** Se a API divergir da documentada, corrigir `BASE`/parâmetros mantendo o endereço fixo no código.
- [ ] **Step 3:** Commit `fix(alexa): alinhado à API real`. **Portão P6 [VOCÊ]**.

### Task 19: Cérebros: troca automática provada de ponta a ponta
**Files:** Create `tests/test_brains_failover_http.py`.
- [ ] **Step 1:** Subir dois servidores HTTP locais falsos (principal devolve 429/500/queda; reserva responde) e provar: `test_principal_cai_reserva_responde`, `test_resposta_ja_iniciada_nao_troca`, `test_cooldown_45s_respeitado`, `test_todos_falham_mensagem_simples`.
- [ ] **Step 2–4:** Corrigir o que falhar; passar.
- [ ] **Step 5:** Commit `test(cérebros): failover provado por HTTP`.

### Task 20: Aprender: teto de custo e 3 dias de uso
**Files:** Create `tests/test_studies_budget_days.py`; Modify `src/jefrey/core/studies.py` se necessário.
- [ ] **Step 1:** Testes com relógio falso: `test_teto_diario_007_para_o_estudo_e_reinicia_no_dia_seguinte`, `test_fonte_do_usuario_e_lida_antes`, `test_texto_do_site_nao_vira_instrucao`.
- [ ] **Step 2–4:** Passar. **[VOCÊ]** usa 3 dias reais e confere o painel de custo (Portão P1).
- [ ] **Step 5:** Commit.

---

# FASE F — Distribuição e comercial (C8, C9, C10)

### Task 21: `release.py` — um comando para publicar
**Files:** Create `scripts/release.py`, `tests/test_release.py`.
**Interfaces:** Produces `plan_release(version: str, url_base: str) -> list[str]` (passos) e `main()` que: valida versão maior que a anterior, roda a suíte, `npm run build:api`, `build_exe.bat`, assina instalador, gera `manifest.json` com `scripts/sign_update.py`, copia tudo para `release/<versão>/`.
- [ ] **Step 1:** Testes: `test_recusa_versao_menor_ou_igual`, `test_manifest_assinado_confere_com_a_chave_publica`, `test_nao_inclui_chave_privada_nem_google_secret_em_release`.
- [ ] **Step 2–4:** Implementar e passar.
- [ ] **Step 5:** Commit `feat(release): script de publicação`.

### Task 22: Assinatura do instalador e do `.exe`
**Files:** Modify `packaging/build_exe.bat` (já assina com `JEFREY_SIGN_PFX`), `docs/PUBLICAR.md`.
- [ ] **Step 1:** **[VOCÊ]** compra o certificado (OV/EV) e define `JEFREY_SIGN_PFX`/`JEFREY_SIGN_PASS`.
- [ ] **Step 2:** Executor roda o build; verifica `signtool verify /pa dist\Jefrey\Jefrey.exe packaging\Output\Jefrey-Setup.exe` → "Successfully verified".
- [ ] **Step 3:** Instalar em PC sem o certificado: SmartScreen não mostra "editor desconhecido" (EV) ou reputação cresce (OV). Registrar no `docs/PORTOES.md` (P7).
- [ ] **Step 4:** Commit `docs: assinatura verificada`.

### Task 23: Atualização automática ponta a ponta
**Files:** Create `tests/test_update_e2e.py`; Modify `docs/PUBLICAR.md`.
- [ ] **Step 1:** Teste com servidor https falso e instalador de teste de 1,1 MB assinado: `test_check_baixa_confere_e_chama_instalador`, `test_assinatura_errada_nao_instala`, `test_hash_errado_apaga_o_arquivo`, `test_versao_igual_ou_menor_ignorada`.
- [ ] **Step 2:** **[VOCÊ]** hospeda `manifest.json` + instalador (site ou GitHub Releases) e coloca o endereço em `packaging/defaults/update_url.txt`; o executor gera 1.0.0 e instala 0.9.x → clica "Atualizar agora" (Portão P7).
- [ ] **Step 3:** Commit.

### Task 24: Instalador: tamanho, atualização silenciosa e desinstalação
**Files:** Modify `packaging/jefrey.iss`, `packaging/build_exe.bat`; Test `tests/test_installer_script.py`.
- [ ] **Step 1:** Testes de texto sobre o `.iss`: `test_pergunta_antes_de_apagar_dados` (desinstalador pergunta "Manter suas memórias?" com padrão Sim), `test_atualizacao_fecha_e_reabre`, `test_extensao_vai_para_documentos`.
- [ ] **Step 2:** Reduzir tamanho: faster-whisper/ctranslate2 como download opcional **só se** a escuta continuar funcionando sem internet no primeiro uso (decisão: manter embutido se a escuta for essencial; medir antes de decidir). Registrar a decisão em `docs/PORTOES.md`.
- [ ] **Step 3:** Commit.

### Task 25: Limpeza de código não usado (P-07)
**Files:** Remover/isolar `src/jefrey/mcp/` (se não usado), `eventbus`, `plugins`, `vision` (confirmar por `grep` que ninguém importa); Test `tests/test_sem_codigo_morto.py`.
- [ ] **Step 1:** Listar cada módulo candidato com `grep -rn "import .*modulo"`; só remove o que tem zero importações e zero rotas registradas.
- [ ] **Step 2:** Remover em commits pequenos (um módulo por commit); a suíte inteira passa a cada um; instalador menor (medir MB antes/depois).
- [ ] **Step 3:** Commit `chore: remove código sem uso (P-07)` por módulo.

### Task 26: Textos legais, licenças e `Jefrey-Pronto` reproduzível
**Files:** Modify `src/jefrey/legal/*` (campos `[NOME DA EMPRESA]`, `[CNPJ]`, `[E-MAIL DE CONTATO]`), `docs/LICENCAS_TERCEIROS.md` (regenerar com `scripts/gen_licenses.py`); Create `scripts/pack_pronto.py`, `tests/test_pack_pronto.py`.
- [ ] **Step 1:** **[VOCÊ]** fornece razão social, CNPJ, e-mail de suporte; **[VOCÊ]** contrata revisão jurídica. O executor preenche e aumenta a versão dos textos (data).
- [ ] **Step 2:** Teste: `test_nenhum_campo_entre_colchetes_nos_textos`, `test_pack_pronto_nao_tem_segredos` (procura `.env`, `*.pfx`, `private`, `google_oauth.json` fora do instalador), `test_pack_pronto_e_reproduzivel` (duas execuções, mesma lista de arquivos).
- [ ] **Step 3:** Implementar `pack_pronto.py` (`git archive` + instalador + `LEIA-ME.txt`).
- [ ] **Step 4:** Commit.

---

# FASE G — Piloto e fechamento

### Task 27: Piloto fechado (3 a 5 pessoas) — roteiro e coleta
**Files:** Create `docs/PILOTO.md`; Modify `docs/PORTOES.md`.
- [ ] **Step 1:** Roteiro: 5 pessoas (≥ 2 acima de 65 anos), tarefa única "instale e peça o Jefrey para lembrar de beber água", observação sem ajudar, cronômetro, anotar onde travou.
- [ ] **Step 2:** **[VOCÊ]** aplica; registrar na tabela de `docs/PORTOES.md` (tempo, travas, nota de voz 1–5).
- [ ] **Step 3:** Cada trava vira uma tarefa nova (issue) priorizada; repetir até o critério de P1 (4 de 5).

### Task 28: Bateria de 17 perguntas com chave real e uso de 3 dias
**Files:** Modify `tests/smoke/` (já existe), `docs/PORTOES.md`.
- [ ] **Step 1:** **[VOCÊ]** conecta uma conta de nuvem; o executor roda a bateria no `.exe` instalado e anota respostas inadequadas.
- [ ] **Step 2:** Corrigir persona/ferramentas conforme os erros; repetir até 17/17 aceitáveis.
- [ ] **Step 3:** Commit.

### Task 29: Fechamento 1.0.0
**Files:** Modify `src/jefrey/__init__.py` (`__version__ = "1.0.0"`), `CHANGELOG.md`, `docs/CHECKLIST_LANCAMENTO.md`, `README.md`.
- [ ] **Step 1:** Todos os portões P1–P7 marcados "passou" em `docs/PORTOES.md`; suíte completa, `tsc`, `vitest` e `pip-audit` verdes; `scripts/verify_installed.py` 100% OK no instalador final.
- [ ] **Step 2:** `scripts/release.py 1.0.0` → instalador assinado + manifesto; `scripts/pack_pronto.py` → `Desktop\Jefrey-Pronto`.
- [ ] **Step 3:** Tag `v1.0.0`, PR `fase-0-limpeza` → `main` (`gh` não está instalado: abrir pelo link de comparação do GitHub).
- [ ] **Step 4:** Commit `release: 1.0.0`.

---

## Portões (aceite que só pessoas e contas reais fecham)
| Portão | Quando | Quem | Passa se |
|---|---|---|---|
| P1 | após T12, T20, T27 | você + 5 pessoas | 4 de 5 concluem instalação e primeira conversa sem ajuda; 3 dias de uso sem travar |
| P2 | após T4–T6 | você + 5 ouvintes | naturalidade ≥ 4/5; fala começa em ≤ 1,5 s |
| P3 | após T7 | você | pulso acompanha a voz; ≥ 50 fps |
| P4 | após T9–T11 | você | 10 comandos reais, inclusive "crie um cubo no Blender", executados com aprovação |
| P5 | após T16 | você | Google 1 clique com cliente Desktop; OpenRouter 1 clique |
| P6 | após T16–T18 | você | agenda real, WhatsApp real, Alexa real |
| P7 | após T22–T23 | você | instalador sem aviso de editor desconhecido; atualização 0.9→1.0 em PC limpo |

## Autoavaliação do plano
- **Cobertura:** C1→T12–T15,T27; C2→T4–T6; C3→T7; C4→T8–T11; C5→T16,T19; C6→T16–T18; C7→T20; C8→T21–T24; C9→T26; C10→T25,T26 e o `pip-audit` no T29. Sem critério sem tarefa.
- **Passos:** cada passo de código traz assinatura, arquivo e teste com nome e asserção; passos **[VOCÊ]** marcam onde o executor para.
- **Consistência de nomes:** `uiautomation.type_text`/`hotkey`/`foreground` (T8) são os usados em T9; `/voice/engines` e `/voice/speak` (T5) são os usados em T6; `cloudvoice` (existente) é reaproveitado, não duplicado.
- **Riscos de escopo:** T11 (conectores) e T25 (código morto) são os maiores; ambos têm lista fechada ou critério de zero importações, e podem ser adiados sem bloquear 1.0.0 se os portões P4 e de tamanho forem aceitos com o escopo reduzido (decisão sua).
