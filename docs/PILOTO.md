# Piloto fechado (3 a 5 pessoas)

Objetivo: provar o critério C1 — uma pessoa de 70 anos instala, configura e usa o Jefrey sozinha, por voz.

## Antes de cada sessão
1. PC com Windows 10/11 **sem** Jefrey, sem Docker rodando na porta 8000 e sem Python.
2. Pen drive com `Jefrey-Setup.exe` (de `Jefrey-Pronto\instalador`). Uma conta de nuvem já pronta para a pessoa (OpenRouter ou ChatGPT).
3. Caneta, cronômetro e a tabela de `docs/PORTOES.md` (Registro).
4. Rode `python scripts/verify_installed.py http://localhost:PORTA` depois da instalação: tudo deve dar OK.

## Quem convidar
5 pessoas; pelo menos 2 com mais de 65 anos e 1 que nunca usou assistente de voz. Nenhuma pode ter ajudado a construir o Jefrey.

## A tarefa (uma só)
> "Instale o programa e peça ao Jefrey para te lembrar de beber água daqui a 30 minutos."

Regras de quem observa: **não ajudar**, não apontar na tela. Só responder "o que você faria?". Se passar de 3 minutos parada na mesma tela, anotar "travou" e dar a dica mínima.

## O que anotar
| Medida | Como |
|---|---|
| Tempo até a 1ª resposta falada do Jefrey | cronômetro |
| Onde travou (tela e frase) | caneta |
| Falou com o microfone sem ajuda? | sim/não |
| Entendeu a voz do Jefrey? Nota de naturalidade | 1 a 5 |
| O que a pessoa disse que esperava e não aconteceu | frase literal |
| Usou o botão Parar / pediu ajuda? | sim/não |

## Critérios de passe (Portão P1)
- 4 de 5 concluem a tarefa sem ajuda.
- Média de naturalidade da voz ≥ 4 (Portão P2).
- Nenhum erro com palavra técnica na tela (".env", "porta", "token").

## Depois
Cada trava vira uma correção, priorizada pela quantidade de pessoas que travaram ali. Repetir com outras 3 pessoas até passar. Registrar tudo em `docs/PORTOES.md`.

## Uso real por 3 dias (Portão P1, parte 2)
Uma pessoa usa por 3 dias: lembretes, perguntas por voz, "Aprender". No fim, conferir: o painel de custo dos estudos (teto US$ 0,10/dia), se alguma resposta estava errada ou inadequada e se o Jefrey abriu sozinho depois de reiniciar o PC.
