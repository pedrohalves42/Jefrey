---
name: jefrey-build-exe
description: Compilar o Jefrey.exe (PyInstaller) e o instalador (Inno Setup) no Windows. Use quando o usuário pedir build, instalador, .exe ou release.
---

# Build do Jefrey (Windows)

Arquivos: `packaging/build_exe.bat`, `build/Jefrey.spec`, `packaging/jefrey.iss`, saída em `dist/` e `packaging/Output`.

## Passos
1. Testes completos passando (skill `jefrey-testar`). Sem exceção.
2. Encerre instâncias antigas: `Get-Process Jefrey -ErrorAction SilentlyContinue | Stop-Process` e processos `python` com `src.jefrey`.
3. Rode o build **em segundo plano**, com log em arquivo, usando o Python 3.12 (`C:\Users\Pedro\jv312`):
   `cmd /c packaging\build_exe.bat > C:\Users\Pedro\build_exe.log 2>&1`
4. Espere com `until grep -qiE "completed successfully|error" /c/Users/Pedro/build_exe.log; do sleep 10; done`.
5. Teste o resultado em home isolada: `C:\Users\Pedro\jefrey_home_<nome>`; o app usa a porta 8000 ou a próxima livre.
6. Só então compile o instalador `.iss`, se pedido.

## Armadilhas conhecidas
- Caminhos de `--icon` e `--add-data` no PyInstaller são relativos ao `.spec` (pasta `build\`): use caminho absoluto.
- Caminhos acima de 260 caracteres falham: use `C:\Users\Pedro\jv312` e `dist\`, nunca o diretório temporário longo da sessão.
- Docker Desktop é instável nesta máquina: o caminho oficial é o modo nativo (`python -m src.jefrey.native`).
- Não assine nem publique sem pedido explícito do usuário.
