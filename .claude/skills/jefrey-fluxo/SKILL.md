---
name: jefrey-fluxo
description: Fluxo padrão de trabalho para qualquer tarefa de código no Jefrey (entender, planejar, implementar com teste, verificar, commitar). Use ao começar funcionalidade, correção ou refatoração.
---

# Fluxo de trabalho do Jefrey

1. **Entender**: leia `CLAUDE.md` e o código vizinho antes de editar. Procure o que já existe (Grep) antes de criar algo novo.
2. **Planejar** (só se a tarefa passar de uma sessão ou tocar vários módulos): `superpowers:brainstorming` e depois `superpowers:writing-plans`.
3. **Implementar com teste primeiro** (`superpowers:test-driven-development`). Mudança mínima, no estilo do código ao redor.
4. **Escrever arquivos**: use Write/Edit. Código com barras invertidas nunca por heredoc no Bash.
5. **Verificar** (`superpowers:verification-before-completion`): `jefrey-testar`; se tocou em áreas sensíveis, `jefrey-seguranca`.
6. **Revisar**: `/simplify` (limpeza) e `/code-review` (bugs) na diff.
7. **Commitar** só quando pedido, em branch que não seja `main`. Mensagem no padrão do histórico (`feat(...)`, `fix(...)`, `security:`).
8. Atualize `CHANGELOG.md` se a mudança for visível para o usuário.

## Eficiência
- Busca ampla em muitos arquivos: delegue a um subagente `Explore`. Tarefas independentes: rode em paralelo.
- Comandos acima de 2 min: segundo plano com log.
- Diga o resultado real: o que passou, o que falhou, o que não foi verificado.
