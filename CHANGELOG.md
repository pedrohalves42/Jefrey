# Changelog

O histórico anterior (fases de servidor, Docker/Kubernetes e "Stark 1.6") está no Git; este arquivo cobre só o produto atual.

## [Nao lancado] — app de Windows (branch fase-0-limpeza)

- **App nativo:** instalador (PyInstaller + Inno Setup), janela WebView2, bandeja, atalho Ctrl+Alt+J, atualização assinada.
- **Interface:** cérebro 3D em 80 % da tela, identidade própria (cobre), cor que muda com o dia, modo fácil.
- **Cérebros:** até 10 ao mesmo tempo, funções por cérebro (conversa, ferramentas, rápido, escrita, estudo, resumo) e trabalho em equipe; 9router e Gemini; troca automática quando um falha.
- **WhatsApp:** janela própria dentro do app, leitura da caixa de entrada e das conversas no formato atual da página, envio com aprovação, conversa consigo mesmo como canal de comando.
- **Redes sociais:** janelas do X, Facebook e Instagram, carrosséis, publicação com aprovação (5 por dia, 10 min de intervalo). Ainda não validado em conta real.
- **Visão:** `screen_look` descreve a tela quando a pessoa pede (precisa de cérebro que enxerga). Ainda não validado.
- **Google:** conexão em um botão; agenda, e-mail, tarefas (criar, editar, apagar), contatos e Drive.
- **Arquitetura hexagonal:** `domain/ ports/ application/ adapters/`; `core/` são atalhos finos; testes de arquitetura no CI.
- **Segurança:** servidor só local (Host/Origin), aprovação humana em ações de risco, texto de terceiros tratado como dado, 0 vulnerabilidades de produção nas dependências.
- **Resumo do dia por voz:** "bom dia, o que eu tenho pra hoje?" responde em 2–5 s com agenda, lembretes e clima, sem passar pelo modelo.
- **Aprende com o uso:** 👍/👎 em cada resposta, medidas de tempo e falha por cérebro e ordem dos cérebros pelo desempenho real (a partir de 5 usos); casos 👎 viram testes locais.
- **Desfazer:** "desfaz isso" cancela o último lembrete ou restaura o último arquivo gravado (janela de 24 h); o que não tem volta é dito com clareza.
- **Alertas de assuntos:** um aviso por dia, entre 8 h e 22 h, com uma novidade de cada assunto de interesse.
- **Área de transferência (desligada por padrão):** oferece traduzir, resumir, explicar ou corrigir o texto copiado; nunca cola nada sozinha; ignora o que parece senha ou chave.
- **Plugins:** arquivo `.py` em `config/plugins` só carrega depois da sua aprovação pelo hash do arquivo; alterado depois, bloqueia de novo; as ferramentas do plugin pedem aprovação a cada uso.
- **Registro legível:** `/audit/today` conta, em frases simples, o que o Jefrey fez e barrou nas últimas 24 h.
- **Segurança:** 36 testes de injeção de prompt; `bandit` sem achado de severidade alta; chaves protegidas pelo DPAPI do Windows.
- **Interface:** avatares Robô e Escudo redesenhados, avatar que respira, ações rápidas por momento do dia.
- **Voz:** voz masculina (Antônio) como padrão; reserva local (Faber) quando a voz da nuvem falha; só responde quando é chamado pelo nome.
- **Instalador:** ao atualizar com o Jefrey aberto, pede para ele fechar sozinho e continua.
- **Celular por QR (desligado por padrão):** servidor separado, só na rede local e só por IP; código de uso único de 5 min, bloqueio após 5 erros, sessão por aparelho revogável; ações de risco continuam pedindo aprovação no computador.
- **Não validado ainda:** celular por QR com um celular de verdade, voz em tempo real (precisa de chave Gemini com acesso ao Live), publicação nas redes e visão em conta real.
- **Limpeza (10/10/2026):** removidos Docker, Kubernetes, Grafana, Prometheus, scripts de servidor e documentos históricos.
