# Plano completo de execução, por sessões (sem datas)

Cada sessão tem **entregas**, **critério de pronto** (verificável) e **o que depende de você**. Uma sessão só termina com testes
passando e commit. Tudo o que já foi conversado está aqui; nada ficou de fora.

## Decisões do dono (valem para todo o plano)
- **Tom:** informal, chamando a pessoa pelo nome, para criar proximidade.
- **Aprender:** automático; a pessoa revisa depois em "O que aprendi".
- **Pesquisa em segundo plano:** o Jefrey escolhe os assuntos pela memória e pela curiosidade; objetivo de virar **especialista com
  autoridade e prática aplicável**. Teto de gasto padrão **US$ 0,10 por dia** (ajustável em Configurações; você não informou um valor).
- **Nuvem é o padrão**; local só sugerido se a máquina for capaz. **Conexões simples:** botão que leva ao site, a pessoa entra na conta e
  volta; sem pedir para entender "chave de API" quando houver alternativa.
- **WhatsApp:** pelo navegador (não pela API oficial), ler e responder; envio automático, com pop-up de aprovação quando necessário.

- **Critério de produto (MVP vendável):** uma pessoa de **70 anos** instala, configura e usa **sozinha**, **por voz**, sem ver as
  palavras "chave", "API", "token", "modelo". Toda sessão é aprovada também por este teste (ver "Teste do idoso" abaixo).
- **Voz primeiro:** falar com o Jefrey e ouvir a resposta é o caminho principal; o teclado é o reserva.

## Teste do idoso (vale para toda sessão)
Letra grande (modo "Fácil" ligado por padrão), contraste alto, um botão grande por tela, frases curtas e sem jargão, nenhum erro
técnico na tela (sempre "o que houve" + "o que fazer" + botão), configuração guiada falando e ouvindo, tudo desfazível, e um
"Ajuda" que explica a tela em voz alta. Roteiro de teste: instalar, dizer o nome, conectar o assistente, pedir um lembrete por voz,
ouvir a resposta, e tudo isso sem ajuda.

## Referências usadas (lidas na fonte)
| Tema | Referência | O que adotamos |
|---|---|---|
| Persona | isair/jarvis | Persona com tom definido, proibir saudação vazia, engajar com o assunto, contexto de hora a cada resposta |
| Memória | isair/jarvis (diário, grafo, portão de recordação); Mem0 (extração passiva + deduplicação); Zep/Graphiti (fato novo substitui o antigo, com tempo); Letta (o agente edita a própria memória) | Extração automática, fatos com validade, diário, "portão" que decide quando buscar |
| Pesquisa | GPT Researcher (planeja perguntas, busca, resume fontes, relatório com citações); STORM (artigos estruturados citados) | Ciclo de estudo por tema com fontes |
| Proatividade | OpenClaw (batimento periódico, canais); OpenJarvis (agendador, atualização assinada) | Briefing, tarefas agendadas, orçamento |
| Instalação/segurança | AnythingLLM (um clique, sem conta); OpenJarvis (SSRF, sandbox, atualização assinada) | Instalador simples, leitor de páginas protegido |

---

## Sessão 1: Identidade e presença
**Entregas:** persona informal em português (sem "Olá! Como posso ajudar?"; engaja com o assunto, uma observação leve); a pessoa é
chamada pelo nome (perguntado na primeira execução e aprendido na conversa); **contexto em toda resposta** (data/hora, nome, ferramentas
disponíveis, modelo em uso, estado da memória) para o Jefrey saber o que ele mesmo é e pode; histórico de conversa **persistente**
(hoje some ao fechar o programa).
**Pronto quando:** testes da persona e do contexto passam; reiniciar o programa mantém a conversa; "o que você precisa para funcionar?"
responde com o estado real.

## Sessão 2: Interface Jarvis e avatar personalizável
**Entregas:** forma **Holograma** com **qualquer imagem do usuário** (foto, desenho, personagem) tingida na cor do tema, com anéis de HUD,
linhas de varredura, faixa de luz, cor dividida e falhas, brilho, partículas e inclinação com o mouse; reage ao estado (pensando,
ouvindo, respondendo, aguardando aprovação); silhueta própria como padrão (sem imagens de terceiros: a pessoa escolhe a dela);
controles de varredura, falhas, apagar fundo e inverter; moldura HUD, relógio, saudação pelo nome e atalhos na abertura;
explicação completa do funcionamento (`COMO_O_JEFREY_FUNCIONA.md`).
**Pronto quando:** imagem enviada vira holograma animado e persiste; testes das funções do efeito passam; verificado no navegador.
**Continua nas próximas sessões:** estados "estudando/aprendendo" no avatar (Sessão 7) e página "Como funciona" dentro do programa.

## Sessão 2B: Voz primeiro e modo Fácil (passa à frente das demais)
**Entregas:** conversa por voz **contínua** (fala, detecta o fim da frase por silêncio, responde falando, escuta de novo; interrupção
ao falar por cima); botão de microfone grande e único; **primeira execução falada** ("Oi, eu sou o Jefrey. Como você se chama?");
palavra de ativação "Jefrey" com aviso de que usa o reconhecimento do navegador; som de confirmação real (hoje toca um arquivo de
imagem); resposta falada completa (hoje corta em 4 frases) e voz mais natural quando houver; **modo Fácil** (fonte grande,
contraste, menu reduzido a Conversa/Conexões/Ajuda; "Avançado" escondido); mensagens de erro humanas (sem "Sem token, vá em
Settings"; o login do aparelho é automático); instruções por voz nas telas de conexão.
**Pronto quando:** pedir um lembrete falando e ouvir a confirmação, sem tocar no teclado; teste do idoso passa.

## Sessão 3: Conexões para leigos
**Entregas:** tela **Conexões** com cartões (sem jargão): Assistente (1 clique), Google (Agenda/Gmail), WhatsApp. Cada cartão: botão que
abre o site, a pessoa entra na conta e volta; onde o provedor só oferece chave (Claude, ChatGPT), um guia de 3 passos com botão "Abrir a
página de chaves" e colagem validada na hora; textos do assistente de primeira execução sem termos técnicos; fluxo do Google pronto
(PKCE, `state`) esperando as credenciais do app.
**Pronto quando:** nenhum texto da tela de conexão contém "API", "modelo", "provedor" sem explicação; testes dos fluxos passam.
**Depende de você:** criar o app OAuth do Google (credenciais) e, para Gmail público, a verificação do Google.

## Sessão 4: Aprendizado automático
**Entregas:** extrator em segundo plano (fila já existente) que tira fatos, preferências, pessoas, projetos e datas de cada conversa;
deduplicação e **atualização temporal** (fato novo substitui o antigo, com histórico); filtros de privacidade (nunca guarda senhas,
documentos de identidade, cartões; saúde e dinheiro só com marca de sensibilidade); tela **O que aprendi** (ver, corrigir, esquecer,
desligar); aprender também pela ferramenta quando a pessoa pede.
**Pronto quando:** conversa de teste gera os fatos certos, sem duplicar, sem guardar segredos; esquecer apaga de fato.

## Sessão 5: Recordação inteligente
**Entregas:** **portão de recordação** (só busca na memória quando ajuda: economiza tempo e custo); **diário** (resumo por dia);
perfil resumido da pessoa; **"Lembrei de…"** sob as respostas, mostrando de onde veio cada lembrança.
**Pronto quando:** respostas usam o perfil e as lembranças certas; o chip aparece e leva à lembrança.

## Sessão 6: Estudos em segundo plano (virar especialista)
**Entregas:** detector de interesses (memória + curiosidade); **plano de estudo por tema** (subtemas, nível de domínio); ciclo
GPT-Researcher: planejar perguntas, buscar, **ler páginas com leitor protegido** (bloqueia endereços internos, sem seguir
instruções do texto), resumir com fonte e data, sintetizar um **guia prático aplicável**; orçamento diário e horário de silêncio;
tela **Estudos** (temas, nível, guias, fontes, o que aprendeu hoje); roda só com o programa aberto, ocioso e dentro do orçamento.
**Pronto quando:** um tema de teste produz guia com fontes verificáveis dentro do teto de gasto; texto malicioso numa página não
altera o comportamento; desligar interrompe na hora.
**Depende de você:** chave de nuvem para medir qualidade e custo reais.

## Sessão 7: Proatividade
**Entregas:** **briefing da manhã** (agenda, lembretes, clima, o que estudou); avisos úteis sem incomodar (limite diário, silêncio);
estados no avatar ("pensando", "estudando", "aprendendo"); notificações do Windows.
**Pronto quando:** briefing gerado no horário escolhido e dispensável; nenhum aviso fora do limite.

## Sessão 8: Ferramentas completas na nuvem
**Entregas:** com modelo de nuvem, oferecer **todas** as ferramentas (hoje há seleção por palavra-chave, feita para modelos pequenos);
busca na web gratuita embutida; leitor de páginas reutilizado da Sessão 5; respostas de ferramentas citando fonte.
**Pronto quando:** "cotação do dólar hoje" e "notícias de X" usam a web e citam a fonte.

## Sessão 9: Voz e presença no Windows
**Entregas:** atalho global para chamar o Jefrey; palavra de ativação "Jefrey" (quando viável localmente); ícone de bandeja com
estados; modo conversa mais natural (interrupção já existe).
**Pronto quando:** atalho abre/fecha a janela de qualquer programa; palavra de ativação mede taxa de falso disparo.
**Depende de você:** testar com o seu microfone.

## Sessão 10: WhatsApp Web
**Entregas:** extensão do Chrome que lê a conversa aberta e responde; pareada com o Jefrey por código; **envio automático**
com **pop-up de aprovação** em casos sensíveis (dinheiro, dados pessoais, pedido fora do padrão, baixa confiança); somente contatos
liberados; sem iniciar conversa nem envio em massa; limite de velocidade; texto de terceiros é dado e **não aciona ferramentas**;
aviso do risco de bloqueio do número.
**Pronto quando:** funciona numa página simulada com todos os cenários; o teste real só você faz (QR do celular).
**Depende de você:** conta de teste e celular.

## Sessão 11: Segurança e robustez restantes
**Entregas:** moldura "isto é dado, não instrução" para tudo que entra no prompt (memórias, documentos, estudos); blocos
`except … pass` silenciosos viram registro; `/metrics` e `/api/status` restritos; MCP só em `127.0.0.1` fora do Docker;
código não usado separado ou removido; revisão de privacidade (o que sai do computador, por provedor).
**Pronto quando:** testes de injeção passam; auditoria CIPHER atualizada com o que mudou.

## Sessão 12: Qualidade e testes
**Entregas:** bateria de pedidos leigos rodando com modelo de nuvem; avaliação de aprendizado (acerto das lembranças, fatos
corretos, custo por dia); teste de ponta a ponta no navegador; desempenho em 8 GB; atualização preservando dados.
**Pronto quando:** meta do plano V3 (≥ 15 de 17 pedidos bons, primeira palavra < 3 s na nuvem).
**Depende de você:** chave de nuvem; segundo PC limpo para o instalador (alerta do Windows e antivírus).

## Sessão 13: Distribuição e comercial
**Entregas:** licença (decisão sua; hoje consta MIT, que permite revenda gratuita), termos de uso e política de privacidade dentro do
programa (LGPD); **atualização automática assinada**; assinatura de código (o Brasil não está na assinatura gerenciada da Microsoft:
certificado comercial); página de download; preço (referência: US$ 149/ano ou US$ 349 vitalício); verificação do Google ou
lançamento sem Gmail.
**Pronto quando:** instalar, atualizar e desinstalar sem perder dados, num PC limpo, com versão assinada.
**Depende de você:** certificado, domínio, textos legais revisados por profissional, conta no Google Cloud.
