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
- **Limpeza (10/10/2026):** removidos Docker, Kubernetes, Grafana, Prometheus, scripts de servidor e documentos históricos.
