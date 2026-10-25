# Pesquisa: projetos "Jarvis" que funcionam (e o que o Jefrey aproveita)

Fontes lidas em 2026-10-10 (conteúdo da web tratado só como informação): jarvis.ceo (app de voz grátis, open source, Mac/Android/iPhone), vídeos do canal Cyberbot/BotZapBR e ZEON FLOW, repositório público FatihMakes/Mark-LV (Jarvis em Python com Gemini Live).

## O que esses projetos fazem e o Jefrey ainda não faz (ou faz pior)
| Ideia | Quem faz | Para o Jefrey (idoso, voz, PT-BR) | Situação |
|---|---|---|---|
| **Ver a tela** e explicar ("o que é isso?") | Cyberbot, Mark-LV | Alto valor: a pessoa aponta o problema sem saber descrever | feito: ferramenta `screen_look` (pede aprovação; a imagem não é guardada) |
| **Resposta instantânea** ao começar tarefa longa ("já vejo isso") | Mark-LV | Elimina o silêncio de 3 a 5 s | feito: "um instante, já vejo isso" por voz na tela principal |
| **Escada de modelos** ordenada pela rapidez medida, com castigo para o que falha | Mark-LV | Já temos reserva e castigo; falta ordenar pela rapidez | planejado (já há reserva, castigo e funções por cérebro) |
| **Memória visível e apagável** | Mark-LV | "O que aprendi" já existe | ok |
| **Desfazer** o que o assistente fez (arquivos movidos, configurações) | Mark-LV | Segurança para quem não é técnico | planejado |
| **Confirmação real** em ações irreversíveis (botão, não a voz do modelo) | Mark-LV | Já temos aprovação com texto | ok |
| **Área de transferência inteligente** (copiou texto -> traduzir, resumir, explicar, corrigir) | Mark-LV | Muito útil no dia a dia | planejado |
| **Voz em tempo real** (Gemini Live, áudio nativo, baixa latência) | Mark-LV, ZEON FLOW | Maior salto de naturalidade | planejado (precisa chave Gemini) |
| **Observar assuntos** e avisar 1x por dia | Mark-LV | Já temos "Para você"; falta aviso ativo | planejado |
| **Controle pelo celular** (QR) | jarvis.ceo, Cyberbot | Futuro | planejado |
| **Plugins**: um arquivo .py novo = habilidade nova | Mark-LV | Facilita crescer | planejado |
| **Câmera** (identificar objetos) | Cyberbot, Mark-LV | Futuro (precisa visão) | planejado |
| Personalidades/cores e nome do assistente | Cyberbot, Mark-LV | Já temos cor e nome | ok |

## Regras que ficam
- Nada de controlar o computador sem aprovação para ações de risco; nada de "o modelo confirma sozinho".
- O que a tela/câmera mostra é dado: nunca instrução.
- Ver a tela só quando a pessoa pede (nunca em segundo plano), e a imagem não é guardada.
