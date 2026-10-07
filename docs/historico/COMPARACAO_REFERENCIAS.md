# Jefrey × projetos de referência (estado real)

Comparação feita lendo a estrutura e o README de cada projeto (clonados em `C:\Users\Pedro\jarvis-references`,
fora do repositório) contra o que o Jefrey tem e foi **verificado** (testes, evals e uso no navegador).
Não executei os projetos de referência; "tem" significa que o código existe na árvore deles.

**Resumo honesto: o Jefrey ainda não é melhor em todos os quesitos.** É melhor em segurança, avaliação e
honestidade da interface; está atrás em número de ferramentas e canais, em voz de tempo real e em
aplicativo nativo.

| Quesito | Melhor referência | Jefrey hoje | Quem está na frente |
|---|---|---|---|
| **Aprovação humana de ações de risco** | OpenJarvis tem `security/` e `sandbox/`; os demais não têm | Fluxo completo e **testado com o banco real**: aprovar, negar, expirar, isolamento entre usuários, também por WhatsApp com código | **Jefrey** |
| **Avaliação do produto (evals)** | isair e OpenJarvis têm pastas de evals | 34 casos rodando contra o sistema vivo (segurança, isolamento, memória, ferramentas, streaming) + 430 testes de servidor + 96 de interface | Empate com isair/OpenJarvis; **Jefrey** em cobertura de segurança |
| **Memória** | isair: grafo de memória e diário; OpenJarvis: módulo de aprendizado | Busca por sentido em português medida (embedding escolhido por benchmark), importar documentos, esquecer de verdade, isolamento testado. **Não aprende fatos sozinho** nem tem grafo | **isair/OpenJarvis** em recursos; **Jefrey** em qualidade medida e controle do usuário |
| **Ferramentas** | OpenJarvis: ~45 (navegador, shell, git, PDF, código, imagem, banco); Mark XXXIX: controle do PC e da tela | 40 no catálogo de risco (notas, hora, conta, clima, arquivos, Google). **Sem navegador, shell/código, tela, PDF** | **OpenJarvis / Mark XXXIX** |
| **Canais** | OpenJarvis: 30+ (WhatsApp, Telegram, Slack, Discord, e-mail...) | WhatsApp (API oficial) implementado e testado com payloads; **sem teste com conta real**; sem os demais | **OpenJarvis** |
| **Voz** | isair: palavra de ativação, detecção de eco, rosto animado; Local-AI-Companion: VAD→Whisper→Kokoro→RVC em tempo real | Ouvir (Whisper local, validado com áudio real), falar (vozes do Windows), interromper, conversa contínua. **Sem palavra de ativação local**, sem TTS neural, latência não é "tempo real" | **isair / Local-AI-Companion** |
| **Visão (tela, câmera)** | isair, Mark XXXIX, Jarvis-AI | Não tem | **Referências** |
| **Interface** | isair (app Qt com rosto), Local-AI-Companion (Live2D) | Web/PWA com cérebro 3D personalizável, status e métricas **reais** (sem números inventados), acessível e responsiva | Preferência pessoal; **Jefrey** em honestidade dos dados |
| **Privacidade** | isair: 100% local | Local por padrão; voz sem Web Speech API; nuvem só se você configurar | Empate com isair |
| **Instalação** | OpenJarvis: instalador de um comando; isair: `.exe` | `start_jefrey.bat` (duplo clique), modo leve, `doctor`, PWA instalável. **Exige Docker Desktop** (pesado em PCs fracos) | **isair / OpenJarvis** |
| **Aplicativo nativo** | isair: app desktop com bandeja | Só PWA (janela instalável); sem bandeja nem atalho global | **isair** |
| **Agentes proativos** | OpenJarvis: resumo matinal, monitor, pesquisa profunda | Não tem | **OpenJarvis** |
| **Backup e diagnóstico** | — (não encontrei nas referências) | `backup`/`restore` com segurança de zip, `doctor` | **Jefrey** |

## O que falta para superar as referências (ordem sugerida)

1. **Ferramentas de alto valor**: navegador controlado e execução de código **em sandbox**, ambos com aprovação.
2. **Voz**: palavra de ativação local e TTS neural (Kokoro) para falar melhor e mais rápido.
3. **Canais**: validar o WhatsApp com conta real; depois Telegram e e-mail.
4. **Agentes proativos**: resumo matinal e monitoramento, sempre sob as mesmas regras de aprovação.
5. **Instalador que dispensa Docker** (modo leve com SQLite) e app nativo com bandeja e atalho global.
6. **Aprendizado de memória**: extrair fatos das conversas (com confirmação) e consolidar.

## Como foi medido

- `python evals/run_evals.py` (sistema vivo) e `python -m pytest tests -q`, `npm test` em `ui/`.
- Modelos de chat e de embedding comparados no mesmo notebook (i7 de 8ª geração, 16 GB, sem GPU): [MODELOS.md](MODELOS.md).
