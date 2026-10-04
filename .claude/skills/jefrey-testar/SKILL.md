---
name: jefrey-testar
description: Rodar e interpretar os testes do Jefrey (pytest hermético, tsc e vitest da UI). Use antes de commitar, após mudar código em src/ ou ui/, ou quando o usuário pedir "rodar testes", "validar" ou "está passando?".
---

# Testar o Jefrey

Python do projeto: `C:\Users\Pedro\jv312\Scripts\python.exe` (3.12). Nunca o 3.14 global.

## Escolha o menor conjunto que prova a mudança
1. **Durante o desenvolvimento**: só o arquivo afetado.
   `C:\Users\Pedro\jv312\Scripts\python.exe -m pytest tests/test_<area>.py -q -p no:cacheprovider`
2. **Antes de commitar** (obrigatório, ~75 s, rode em segundo plano com log em arquivo):
   `C:\Users\Pedro\jv312\Scripts\python.exe -m pytest tests -q --ignore=tests/e2e --ignore=tests/smoke`
3. **Se mexeu em `ui/`**: `cd ui && npx tsc --noEmit -p . && npm test`

## Regras
- Comandos longos: `run_in_background` e `until grep -q "passed\|failed\|error" log; do sleep 10; done`.
- Falhou? Leia a causa raiz (skill `superpowers:systematic-debugging`); não ajuste o teste para passar.
- Mudou autenticação, CORS, Host/Origin ou ferramentas de risco: rode também
  `tests/test_local_guard.py`, `tests/test_google_oauth_state.py` e os testes de aprovação (`tests/test_approvals_auth.py`).
- Nunca rodar `ruff --fix` em massa sem rodar a suíte completa depois.
- Relate o resultado real (contagem de passou/falhou); se pulou algo, diga.
