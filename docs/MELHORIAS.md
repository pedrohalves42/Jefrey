# O que podemos melhorar (lista priorizada)

Critério: uma pessoa de 70 anos instala, configura e usa sozinha, com a voz.

## A. Só você pode fazer (bloqueiam a venda)
| # | Item | Por quê |
|---|---|---|
| A1 | Colocar `packaging/defaults/google_oauth.json` (e e-mail como testador) antes de gerar o instalador | Sem isso "Entrar com o Google" pede configuração técnica |
| A2 | Testar com 3 a 5 pessoas reais (piloto fechado), incluindo uma de 70 anos | Nenhum teste automático substitui isso |
| A3 | Bateria de 17 perguntas com chave de nuvem real | Só provamos a lógica com modelo falso |
| A4 | Testar voz com microfone e caixa de som reais, e ver o pulso do avatar falando | Só verificado em código e testes |
| A5 | Testar a Alexa com conta real (Voice Monkey) | A API não foi verificada com conta real |
| A6 | Certificado de assinatura de código | Sem ele o Windows avisa "editor desconhecido" |
| A7 | Servidor de atualizações + chave de assinatura (`update_url.txt`, `update_public_key.txt`) | Atualização automática fica desligada sem eles |
| A8 | Revisão dos textos legais (termos e privacidade) por advogado | Obrigação LGPD |
| A9 | Publicar a extensão do WhatsApp na Chrome Web Store | Hoje precisa "Carregar sem compactação" |
| A10 | Verificação do app no Google (só Agenda) | Sem ela, limite de 100 testadores e aviso |
| A11 | Licença, cobrança e domínio | Modelo de venda |

## B. Produto (próximos passos de código)
1. **Primeira abertura guiada só por voz**: o Jefrey fala e a pessoa responde, sem teclado.
2. **Mais comandos do computador**: fechar programa, escrever em programa aberto, captura de tela explicada (hoje: abrir programa, site, pasta e volume).
3. **Alexa**: descobrir dispositivos automaticamente (depende do item A5).
4. **Cérebro local guiado**: baixar o modelo local com um botão para quem não quer chave.
5. **Modo "família"**: um cuidador recebe um resumo semanal (com consentimento da pessoa).
6. **Lembretes por voz com repetição** até a pessoa confirmar.
7. **Acessibilidade**: tamanho de letra maior no avatar/legendas, alto contraste, teste com leitor de tela.
8. **Telemetria sem dados pessoais** (opcional, com aceite) para achar onde as pessoas travam.

## C. Qualidade e dívida técnica
1. P-03: atualizar `langchain-core`/`openai` (vulnerabilidades conhecidas das dependências).
2. P-07: remover código não usado (MCP, eventbus, plugins, visão) para reduzir superfície e tamanho (~130 MB).
3. Testes ponta a ponta no `.exe` instalado automatizados (hoje manuais).
4. Instalador menor: separar faster-whisper/ctranslate2 como download opcional.
5. Docker: manter só como opção avançada (instável nesta máquina).
