# CHANGELOG - Jefrey Project

All notable changes to this project will be documented in this file.

## v1.6.3-futurista-100 (2026-09-05)

### Added
- **CIPHER-204**: KnowledgePage UI — página dedicada de conhecimento pessoal com CRUD completo (busca semântica, listagem recente, criar/editar/deletar notas), isolamento multi-tenant por `user_id` (Axiom #2), integração com `NotesSkill` (6 tools) via MCP `/mcp/tools/{tool}`, UI glassmorphism Stark-mode com Tabs (Buscar/Recentes/Criar), navegação via rota `/knowledge` em `App.tsx` e link no `Nav.tsx`.

### Changed
- **`ui/src/App.tsx`**: Adicionada import `KnowledgePage` e rota `<Route path="/knowledge" element={<Knowledge/>} />`.
- **`ui/src/components/Nav.tsx`**: Adicionado link `{ to: "/knowledge", label: "Conhecimento" }` no array de links.
- **`ui/src/pages/KnowledgePage.tsx`**: Novo arquivo (379 linhas) com páginas de busca, recentes e criação/edição de notas, usando componentes shadcn-ui (input, textarea, tabs, dialog, select, badge) e `apiFetch` com `authHeaders()` que já injetava `X-User-Id` (CIPHER-031/033 compliance).

### Fixed
- UI build passou após adicionar componentes shadcn-ui (input, textarea, tabs, dialog, label, select) via `npx shadcn@latest add`.

### Gates
- 175/175 deep checks ✅, 32/32 CIPHER fixes ✅, 40 pytest ✅, docker compose RC0 ✅.