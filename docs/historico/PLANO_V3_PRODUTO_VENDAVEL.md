# Plano V3: do protótipo ao produto vendável (04/10/2026)

Substitui o "Estado real" de `PLANO_PRODUTO_COMPLETO.md`. Evidências: auditoria com 17 pedidos de usuário leigo,
teste em máquina limpa, testes automáticos (591 de servidor, 99 de interface) e [PESQUISA_PROJETOS.md](PESQUISA_PROJETOS.md).

## Decisões do dono
1. **Nuvem como padrão.** Se o computador tiver capacidade, o Jefrey **sugere** o melhor modelo local para aquela máquina.
2. **Público: pessoas comuns.** Não se vende pelo WhatsApp e **não se usa a API do WhatsApp**. O Jefrey usa o **WhatsApp Web no navegador** para atender os contatos da própria pessoa.
3. **WhatsApp: apenas ler e responder conversas.** Sem envio em massa, sem iniciar conversas.

## Verdades medidas que sustentam as decisões
| Fato | Medição |
|---|---|
| Modelo local pequeno não serve de padrão | `qwen3:1.7b` (rápido, 2 a 30 s): errou a Copa de 2022, inventou lugares, errou tradução |
| Modelo local bom é lento sem GPU | `gemma4:e2b` (4,6 GB): acertou tradução, Copa, memória, e-mail; **35 a 130 s por resposta** em i7 de 8ª geração, 16 GB, sem GPU. `llama3.1:8b`: 50 a 146 s |
| Atalhos em código são rápidos e não erram | hora, conta, lembretes, notas, listar notas: ~2 s |
| Docker é inviável para leigos | o Docker Desktop encerrou o próprio processo 7 vezes numa sessão |
| Sem GPU testada | a sugestão de modelo local para máquinas com GPU/Apple Silicon **não foi medida** (não temos esse hardware) |

## Estado real
**Pronto e verificado:** modo nativo sem Docker (sobe em ~6 s numa pasta limpa; teste de máquina limpa), lançador
automático, lembretes reais, notas por voz de comando ("guarda isso", "o que anotei"), memória por sentido,
aprovação humana de ações de risco, proteção contra ataque pelo navegador (Host/Origin), portas fechadas no Docker,
ferramentas do Google só com conta conectada, importação de documentos, `doctor`, backup/restauração, voz local,
interface com cérebro 3D, suíte hermética (59 s, sem Docker).

**Parcial:** `.exe` empacotado (466 MB, **testado antes de duas correções; falta retestar**), PWA (service worker
testado só por unidade), Google (código existe, **não validado com conta real**), canal WhatsApp por API
(código completo; **será removido/arquivado pela decisão 2**).

**Não começou:** onboarding de nuvem (colar chave, testar), padrão de nuvem no produto, sugestão de modelo local por
hardware real (GPU/VRAM), extensão do Chrome para WhatsApp Web, instalador `.exe` (Inno Setup), assinatura, atualização
automática assinada, licença/termos/privacidade, verificação do app no Google, navegador e código em sandbox,
agentes proativos, voz com palavra de ativação.

## Arquitetura alvo
```
Instalador (.exe) -> Jefrey (modo nativo, só no PC do usuario: SQLite, memoria local)
   |-- Modelo: NUVEM por padrao (Claude/ChatGPT/Gemini, chave do usuario ou assinatura)  +  LOCAL sugerido por hardware
   |-- Voz local, lembretes, notas, memoria, documentos
   |-- Extensao do Chrome (WhatsApp Web) <-> Jefrey por localhost, pareada por codigo
```

## Etapas e critério de "pronto"
**E1. Funciona de verdade (antes de qualquer venda)**
- Primeira execução pergunta "Como quer usar?": nuvem (colar chave, botão "Testar") ou local; sem jargão.
- Detector de hardware sugere modelo local só com GPU ou Apple Silicon adequados; sem isso, recomenda nuvem e diz por quê.
- Re-rodar a bateria de 17 pedidos com um modelo de nuvem e **registrar acertos e tempo** (meta: ≥ 15 de 17 bons, primeira palavra < 3 s).
- Retestar o `.exe` em pasta limpa e em outro PC Windows.
- **Pronto quando:** pessoa sem conhecimento técnico, num PC limpo, chega à primeira resposta em ≤ 5 minutos sem terminal.

**E2. Instalável por leigo**
- Instalador Inno Setup sobre o PyInstaller; instala Ollama só se o usuário escolher modo local.
- Assinatura de código (certificado comercial; a assinatura gerenciada da Microsoft não cobre o Brasil) e plano para o aviso do SmartScreen.
- Atualização automática **assinada** (padrão do OpenJarvis: chave pública embutida, verificação antes de instalar).
- Desinstalar sem deixar lixo; backup antes de atualizar.

**E3. WhatsApp Web (extensão do Chrome), desenho de menor risco**
- A IA **lê** a conversa aberta e **sugere** a resposta; a pessoa revisa e envia (modo padrão).
- Modo automático só opcional, com aviso do risco de bloqueio do número, limite de velocidade e lista de contatos permitidos.
- Mensagens de terceiros são **entrada não confiável**: geram só texto; nenhuma ferramenta é acionada por elas.
- Pareamento por código entre a extensão e o Jefrey; a proteção local passa a aceitar apenas a origem da extensão pareada.
- Aviso de privacidade: com modelo de nuvem, o texto dos clientes sai do computador.
- **Pronto quando:** testado com uma conta real de WhatsApp (a nossa, não a de um cliente), com os riscos documentados na própria tela.

**E4. Comercial**
- Licença do software (hoje diz MIT, que permite revenda gratuita; **decidir**), termos de uso, política de privacidade (LGPD).
- Preço: referência Msty = grátis / US$ 149 por ano / US$ 349 vitalício.
- Verificação do app no Google (Gmail é escopo restrito) ou lançar sem Gmail.
- Suporte: `doctor`, relatório de diagnóstico que o cliente envia, canal de atendimento.
- Auditoria de segurança independente (hoje só nossa).

**E5. Qualidade contínua**
- Evals rodando em cada versão (34 casos hoje; acrescentar os 17 pedidos leigos).
- Voz com palavra de ativação, navegador e código em sandbox, agentes proativos.

## Perguntas em aberto
1. **Quem paga a nuvem?** Chave do próprio usuário (simples para nós, mais difícil para leigos) ou assinatura nossa (mais fácil, exige servidor, cobrança e custo por uso).
2. **WhatsApp automático:** liberar o modo automático (com aviso) ou manter só "sugerir"?
3. **Licença** do Jefrey.
