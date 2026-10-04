# Distribuição e venda: o que está pronto e o que falta (04/10/2026)

## Pronto no código
- **Instalador** (`packaging\build_exe.bat` → `packaging\Output\Jefrey-Setup.exe`): instala por usuário, sem pedir administrador; os dados da pessoa ficam em `%LOCALAPPDATA%\Jefrey` e **não** são apagados ao desinstalar. Leva a extensão do Chrome em `extensao-chrome`.
- **Termos de uso e Política de Privacidade** dentro do programa (primeira tela: "Li e aceito"), e **Privacidade**: ver o que é guardado, baixar uma cópia, apagar tudo (LGPD). Textos em `src/jefrey/legal/` (rascunhos).
- **Atualização automática assinada** (`core/updater.py`, `scripts/sign_update.py`): confere assinatura Ed25519 e SHA-256, não aceita versão igual/antiga, faz backup antes, só instala quando a pessoa clica.
- **Assinatura de código** no `build_exe.bat` (variáveis `JEFREY_SIGN_PFX` e `JEFREY_SIGN_PASS`).
- **Licenças de terceiros**: `docs/LICENCAS_TERCEIROS.md` (gerado por `scripts/gen_licenses.py`): nenhuma de copyleft forte.
- **Página de apresentação**: `site/index.html` (estática, com o botão de download a preencher).

## O que depende de você (não dá para fazer por aqui)
| # | Item | Como |
|---|---|---|
| 1 | **Certificado de assinatura de código** | Comprar um certificado OV ou EV (por exemplo Certum, Sectigo, DigiCert, SSL.com) e definir `JEFREY_SIGN_PFX`/`JEFREY_SIGN_PASS`. A "assinatura gerenciada" da Microsoft **não cobre o Brasil**. Sem assinatura o Windows mostra "editor desconhecido"; mesmo assinado, o SmartScreen só deixa de avisar depois que o programa ganha reputação (EV dá reputação imediata) |
| 2 | **Par de chaves das atualizações** | `python scripts/sign_update.py --gen-key`; guarde a chave **privada** fora do computador de vendas e do repositório; cole a **pública** em `PUBLIC_KEY_B64` (`core/updater.py`) ou em `config/update_public_key.txt` |
| 3 | **Servidor de atualizações** | Hospedar `manifest.json` e o instalador por **https** (pode ser um bucket estático) e definir `JEFREY_UPDATE_URL` (ou deixar embutido no build) |
| 4 | **Textos legais** | Preencher `[NOME DA EMPRESA]`, `[CNPJ]`, `[E-MAIL DE CONTATO]`, preço e foro, e **revisar com advogado** (LGPD, Código de Defesa do Consumidor). Os rascunhos estão marcados com um comentário `REVISAR` no topo |
| 5 | **Licença do código** | Hoje o repositório está sob **MIT**: quem tiver o código pode redistribuir de graça. Para vender: manter o código **privado** e distribuir só o instalador sob os Termos (EULA), e remover o arquivo MIT do que for público. Decisão sua |
| 6 | **App do Google** | Seguir `docs/GOOGLE.md`: criar o cliente "Aplicativo para computador", publicar e pedir a **verificação** (Gmail é escopo restrito: pode exigir avaliação de segurança anual). Alternativa: lançar só com **Agenda** |
| 7 | **Extensão do Chrome na loja** | Hoje se instala em "modo desenvolvedor" (3 passos). Para 1 clique: publicar na Chrome Web Store (conta de desenvolvedor, taxa única de US$ 5) e trocar o passo a passo por "Adicionar ao Chrome" |
| 8 | **Domínio, página de download e cobrança** | Hospedar `site/` num domínio, escolher o meio de pagamento (referência de mercado: US$ 149/ano ou US$ 349 vitalício; Msty cobra isso) |
| 9 | **Teste em PC limpo** | Instalar o `Jefrey-Setup.exe` numa máquina sem Python/Docker e passar o roteiro abaixo; verificar o antivírus |
| 10 | **Chave de nuvem para medir** | `python evals/run_evals.py --only leigos` com uma chave de nuvem (meta: ≥ 15 de 17 e primeira palavra < 3 s) |

## Roteiro de teste do idoso (PC limpo, sem ajuda)
1. Baixar e instalar (Avançar, Avançar, Concluir). 2. Ler e **aceitar** os termos. 3. Dizer o nome. 4. Apertar **Conectar com 1 clique** e entrar na conta. 5. Tocar em **Toque aqui e fale comigo** e pedir "me lembra de tomar o remédio às oito da noite" falando. 6. Ouvir a confirmação. 7. Fechar e abrir de novo: o lembrete continua.
Aprovado quando a pessoa chega ao passo 6 sozinha em até 10 minutos.

## Publicar uma versão (para quem vende)
1. Subir o número em `src/jefrey/__init__.py`, `pyproject.toml` e `core/config.py`. 2. `packaging\build_exe.bat` (com o certificado). 3. `python scripts/sign_update.py --key update_private_key.txt --installer packaging\Output\Jefrey-Setup.exe --version X.Y.Z --url https://.../Jefrey-Setup-X.Y.Z.exe --notes "..."`. 4. Publicar o instalador e o `manifest.json`. 5. Quem já usa vê "Tem uma versão nova" em **Ajuda > Atualizações**.
