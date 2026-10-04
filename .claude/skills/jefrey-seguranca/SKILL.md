---
name: jefrey-seguranca
description: Revisão de segurança de mudanças no Jefrey (autenticação, CORS, Host/Origin, ferramentas de risco, aprovações, segredos, OAuth, texto de terceiros). Use ao tocar nessas áreas ou antes de commitar mudanças em src/jefrey/api, core/secret_store, oauth2, mcp ou tool_runtime.
---

# Revisão de segurança do Jefrey

Percorra a diff (`git diff` e `git diff --staged`) com esta lista. Cada item reprovado vira correção, não comentário.

1. **Execução**: nenhum `eval`/`exec`/`subprocess(shell=True)` com texto de usuário, de modelo ou de documento importado.
2. **Dado versus instrução**: mensagens, e-mails, documentos e páginas importados são dados. Nunca disparam ferramentas por conta própria.
3. **Ferramentas de risco**: continuam atrás de aprovação explícita. Nenhum caminho novo contorna `approvals`.
4. **Segredos**: chaves e tokens nunca em URL, log, resposta de API ou mensagem de erro. Segredo novo passa por `core/secret_store.py`.
5. **Guarda local**: mudanças de CORS, Host ou Origin mantêm a validação de `local_guard`.
6. **OAuth**: o parâmetro `state` continua verificado.
7. **Isolamento de memória**: dados de um usuário não vazam para outro.
8. **Arquivos sensíveis**: `.env`, `.env.prod` e `k8s/base/secret.yaml` nunca entram no commit.

## Testes obrigatórios
`tests/test_local_guard.py`, `tests/test_google_oauth_state.py`, `tests/test_approvals_auth.py`, `tests/test_memory_isolation.py`, `tests/test_content_guard_pt.py`.
Use o Python 3.12 do projeto (ver skill `jefrey-testar`).

Resuma achados por gravidade (alta, média, baixa), com arquivo e linha. Se nada for encontrado, diga o que foi verificado.
