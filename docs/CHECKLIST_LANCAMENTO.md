# Checklist de lançamento (atualizado em 2026-10-24)

Legenda: ✅ pronto e testado · 🟡 pronto no código, falta prova com conta/pessoa real · ⛔ só o dono do produto consegue

## Produto
| Item | Estado |
|---|---|
| Instalador Windows sem Docker, desinstalador, dados preservados ao reinstalar | ✅ |
| Termos e privacidade com aceite, copiar e apagar dados | ✅ (textos com campos a preencher: ⛔) |
| Conversa por voz (escuta local), avatar grande com pulso, painéis | ✅ / 🟡 pulso com voz real |
| Cérebros: OpenRouter 1 clique, Claude/ChatGPT/Groq/etc. por "colar e conectar", principal + 3 reservas com troca automática | ✅ / 🟡 só testado com respostas simuladas |
| Aprender por pedido, fontes e links, estudos em segundo plano com teto de custo | ✅ |
| Controle do computador (abrir, fechar, pesquisar, música, volume) | ✅ / 🟡 sem modelo real |
| Alexa (Voice Monkey): falar, casa toda, rotinas, listar | 🟡 API nunca testada com conta real |
| Google (Agenda, e-mail, Drive) | 🟡 falta o login real funcionar (redirect_uri) |
| WhatsApp pela extensão do Chrome (pasta em Documentos) | 🟡 falta teste com WhatsApp real |
| Voz natural: escolha automática da melhor voz do PC + voz da nuvem (ChatGPT) | 🟡 / voz local neural (Piper) ainda não feita |
| Atualização automática assinada, com aviso e botão | ✅ código / ⛔ falta o endereço do manifesto |

## Segurança
| Item | Estado |
|---|---|
| Logs sem segredos, tokens em cofre do Windows, sem eval/shell com texto do usuário | ✅ |
| Dependências: pip-audit só aponta o `chromadb` em modo servidor, que não é usado (ver AUDITORIA §5) | ✅ risco aceito |
| Instalador assinado | ⛔ precisa de certificado |

## Acrescentado desde 05/10 (estado real em 24/10/2026)
| Item | Estado |
|---|---|
| Resumo do dia por voz, notícias diretas, desfazer, alertas de assuntos, área de transferência (desligada por padrão) | ✅ testado e validado no app instalado (exceto a área de transferência: só pela API) |
| Aprender pelo uso (👍/👎, medidas por cérebro, ordem pelo desempenho) | ✅ código e medidas; 🟡 efeito da ordem depende de uso real (≥ 5 chamadas por cérebro) |
| Plugins aprovados pelo hash e registro "o que o Jefrey fez hoje" | ✅ |
| Celular por QR (rede local, desligado por padrão) | ✅ servidor testado de verdade na rede; 🟡 falta parear um celular real |
| Modo família (resumo semanal, só com consentimento, envio sempre com aprovação) | ✅ código e testes; 🟡 falta uso real |
| Acessibilidade: letra grande e alto contraste | ✅ código e axe; 🟡 falta conferir com o Narrador do Windows |
| Instalador: atualização por cima com o app aberto | ✅ validado |
| Voz: Antônio (masculina) por padrão; reserva local quando a nuvem falha | 🟡 a voz da Microsoft recusou pedidos (403) em 12/10; a reserva local depende de baixar 60 MB |
| Voz em tempo real | ⛔ precisa de chave Gemini com acesso ao Live |
| Publicação nas redes e visão com conta real | ⛔ falta entrar nas contas |
| Revogar a chave do Google que vazou | ⛔ por último, só o dono |

## Só o dono consegue (sem isso não é "100%")
1. Fazer o login do Google funcionar ponta a ponta (cadastrar o endereço, ou criar o cliente "Aplicativo para computador"), e a verificação do app.
2. Preencher `[NOME DA EMPRESA]`, `[CNPJ]`, `[E-MAIL DE CONTATO]` e revisão jurídica dos textos.
3. Certificado de assinatura de código.
4. Hospedar o `manifest.json` e o instalador; colocar o endereço em `packaging/defaults/update_url.txt`.
5. Guardar uma cópia da chave privada de atualização (`C:\Users\Pedro\Jefrey-chaves`) fora deste computador.
6. Publicar a extensão na Chrome Web Store.
7. Piloto com 3 a 5 pessoas reais (uma de 70 anos) e bateria de 17 perguntas com uma chave de nuvem real.
8. Licença, cobrança e domínio.
9. **Texto de privacidade:** acrescentar que, com a voz natural gratuita, o texto que o Jefrey vai **falar** é enviado ao serviço de voz da Microsoft (vozes neurais do Edge, uso não oficial, sem chave). Alterar `src/jefrey/legal/privacidade.md` pede nova aceitação dos termos pela pessoa, então faça junto com a revisão jurídica. Para um serviço com contrato, trocar por Azure/Google Text-to-Speech (camada gratuita com chave) é uma troca de adaptador em `adapters/outbound/edge_voice.py`.
