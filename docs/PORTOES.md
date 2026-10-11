# Portões de aceite

Um portão só fecha com pessoas e contas reais. Anote cada tentativa na tabela do portão (data, quem, resultado, o que travou).
Antes de qualquer portão: **feche qualquer outro Jefrey** (inclusive uma cópia antiga que ainda esteja aberta), senão ele pode ocupar a porta 8000.
Rode `python scripts/verify_installed.py http://localhost:PORTA` no instalado: tudo deve dar OK.

| Portão | Critério | Passa se |
|---|---|---|
| **P1** Idoso | C1 | 4 de 5 pessoas (2 com mais de 65 anos) instalam e fazem a 1ª conversa por voz sem ajuda; 3 dias de uso sem travar |
| **P2** Voz natural | C2 | nota de naturalidade ≥ 4/5 de 5 ouvintes; fala começa em ≤ 1,5 s |
| **P3** Pulso | C3 | o avatar acompanha o volume da voz; ≥ 50 fps |
| **P4** Controle do PC | C4 | 10 comandos reais, inclusive "crie um cubo no Blender", com aprovação |
| **P5** Conexões | C5 | OpenRouter 1 clique; Claude/ChatGPT/Groq por "colar e conectar"; Google 1 clique (cliente Desktop) |
| **P6** Integrações | C6 | agenda real do Google, WhatsApp real, Alexa real |
| **P7** Distribuição | C8 | instalador sem aviso de "editor desconhecido"; atualização 0.9.x → 1.0.0 em PC limpo |

## Roteiro
**P1:** instale o `Jefrey-Setup.exe` em um PC sem nada. Peça à pessoa: "instale e peça ao Jefrey para te lembrar de beber água". Não ajude; anote o tempo e onde travou.
**P2:** 5 ouvintes escutam 3 frases; nota de 1 a 5 de naturalidade.
**P3:** fale com o Jefrey e veja o avatar pulsar junto com a voz.
**P4:** "abre o Word", "fecha o Chrome", "pesquisa receita de bolo", "pausa a música", "aumenta o volume", "digita olá no Bloco de Notas", "crie um cubo no Blender"…
**P5/P6:** siga `docs/GOOGLE.md` (cliente "Aplicativo para computador"), depois pergunte "o que tenho na agenda amanhã?".
**P7:** `docs/PUBLICAR.md`.

## Registro
| Data | Portão | Quem | Resultado | Travou em |
|---|---|---|---|---|
| | | | | |
