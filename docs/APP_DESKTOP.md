# Jefrey como app de desktop

O Jefrey abre numa **janela propria** (WebView2, o motor do Edge que ja vem no Windows 11), sem barra de endereco nem abas.
O servidor e a tela sao os mesmos de antes; muda so a "moldura".

## Comportamento
| Acao | O que acontece |
|---|---|
| Abrir `Jefrey.exe` | Mostra uma tela de abertura ("Acordando...") e carrega a interface 3D assim que o servidor responde. |
| Fechar no **X** | A janela some, o Jefrey continua no relogio do Windows (ouvindo, lembrando, avisando). Um balao explica isso na 1a vez. |
| Icone do relogio | Abrir / Mostrar o orbe / Ver registros / **Sair** (unico jeito de fechar de vez). |
| Abrir o programa de novo | Nao abre outro: traz a janela existente para a frente (arquivo-sinal em `config\show.signal`). |
| **Ctrl + Alt + J** | Traz a janela e manda o Jefrey ouvir. **Ctrl + Alt + P** para qualquer acao dele no computador. |
| Orbe | Bolinha pequena, sempre visivel, com o cerebro 3D. Mostra o estado (ouvindo, pensando, falando). Clicar abre a janela; arrastar move. |
| Iniciar com o Windows | Em Configuracoes > "O Jefrey no computador". Abre escondido no relogio (`--minimized`). |
| Tamanho e posicao | Lembrados entre aberturas (`config\window.json`), e corrigidos se o monitor mudou. |

## Seguranca
- O microfone e liberado so para a propria tela (127.0.0.1); nada de outros sites.
- Login do Google **nao** acontece dentro da janela (o Google recusa): o botao abre o navegador padrao e a tela espera a volta.
  So enderecos `https` do Google podem ser abertos assim (lista fechada em `shell.EXTERNAL_HOSTS`).
- A janela so fala com o servidor local; a protecao de Host/Origin continua valendo.

## Plano B
- Sem WebView2 ou com `JEFREY_WINDOW=browser`, o programa abre no navegador como antes.
- Se a janela falhar ao iniciar, o launcher registra o erro em `logs\jefrey.log` e abre o navegador.

## Testes manuais (para quem for validar)
1. Abrir, ver o cerebro 3D, falar uma frase (o microfone nao pede permissao).
2. Fechar no X, conferir que o icone do relogio continua; abrir de novo pelo atalho ou pelo icone.
3. Mostrar o orbe, clicar nele.
4. Configuracoes > ligar "abrir com o Windows", reiniciar o computador.
5. Conexoes > Google: o navegador abre; ao concluir, a janela do app mostra "Conectado".
