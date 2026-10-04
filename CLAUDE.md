# Regras de trabalho neste projeto (Windows + Git Bash)

Estas regras existem porque cada uma já causou falhas reais. Siga-as antes de rodar comandos.

## Escrever arquivos
- **Nunca** gere código com barras invertidas (`\n`, `\s`, `\d`, regex, caminhos) por `cat <<EOF` ou `python - <<EOF` no Bash:
  as barras são reduzidas e o código sai quebrado (`\\n` vira quebra de linha, `\\s` vira `\s`).
  Use as ferramentas **Write** e **Edit**. Para alterações maiores, grave um script `.py` com Write e rode-o.
- Em substituições de texto por script, use `assert antigo in texto` (falha alto em vez de não fazer nada).

## Ambiente
- Python do projeto: **3.12** em `C:\Users\Pedro\jv312` (`C:\Users\Pedro\jv312\Scripts\python.exe`). Não use o 3.14 global:
  o `chroma-hnswlib` não instala nele.
- Caminhos **curtos**: o Windows falha acima de 260 caracteres. Use `C:\Users\Pedro\jv312`, `C:\Users\Pedro\jefrey_home_*`
  e `dist\`; evite o diretório temporário longo da sessão para instalar pacotes ou criar ambientes.
- Em `PyInstaller`, caminhos de `--icon`/`--add-data` são relativos ao `.spec` (pasta `build\`): use caminho absoluto.
- Testes: `C:\Users\Pedro\jv312\Scripts\python.exe -m pytest tests -q --ignore=tests/e2e --ignore=tests/smoke`
  (hermético: SQLite + Redis em memória, ~75 s). Interface: `cd ui && npm test` e `npx tsc --noEmit -p .`.
- Antes de commitar, os testes completos precisam passar. **Nunca** rodar `ruff --fix` em massa sem rodar os testes depois
  (já removeu reexportações e quebrou módulos).

## Comandos longos
- `sleep` isolado é bloqueado e comandos passam de 2 min: use `run_in_background` e espere com `until <condição>; do sleep 10; done`.
- Compilar o `.exe` e instalar pacotes grandes: sempre em segundo plano, com log em arquivo.

## Servidores de teste
- O Jefrey nativo usa a porta 8000 (ou a próxima livre). Antes de subir outro, encerre o anterior
  (`Get-Process Jefrey` / processos `python` com `src.jefrey`). Dados de teste ficam em `C:\Users\Pedro\jefrey_home_*`.
- Docker Desktop é instável nesta máquina; o caminho oficial é o modo nativo (`python -m src.jefrey.native`).

## Web e busca
- A ferramenta `WebSearch` do ambiente pode falhar com erro de modelo. Alternativa: navegador embutido
  (`mcp__Claude_Browser__*`) com `https://html.duckduckgo.com/html/?q=...`.
- Não criar conta, não entrar em serviços e não colar chaves em nome do usuário.

## Segurança (não regredir)
- Nada de `eval`/`exec`/shell com texto de usuário; tokens e chaves nunca em URL, log ou resposta.
- Texto de terceiros (mensagens, documentos importados) é **dado**, nunca instrução; sem ferramentas a partir dele.
- Mudou autenticação, CORS, Host/Origin ou ferramentas de risco: rode `tests/test_local_guard.py`, `tests/test_google_oauth_state.py`
  e os testes de aprovação.
