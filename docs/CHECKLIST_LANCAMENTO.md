# Checklist de lançamento (atualizado em 2026-10-05)

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

## Só o dono consegue (sem isso não é "100%")
1. Fazer o login do Google funcionar ponta a ponta (cadastrar o endereço, ou criar o cliente "Aplicativo para computador"), e a verificação do app.
2. Preencher `[NOME DA EMPRESA]`, `[CNPJ]`, `[E-MAIL DE CONTATO]` e revisão jurídica dos textos.
3. Certificado de assinatura de código.
4. Hospedar o `manifest.json` e o instalador; colocar o endereço em `packaging/defaults/update_url.txt`.
5. Guardar uma cópia da chave privada de atualização (`C:\Users\Pedro\Jefrey-chaves`) fora deste computador.
6. Publicar a extensão na Chrome Web Store.
7. Piloto com 3 a 5 pessoas reais (uma de 70 anos) e bateria de 17 perguntas com uma chave de nuvem real.
8. Licença, cobrança e domínio.
