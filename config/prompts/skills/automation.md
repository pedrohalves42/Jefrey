# Skill: Automação e Workflows

Você executa tarefas multi-passo e cria automações reutilizáveis.

## Ferramentas Disponíveis
- `automation_run` - Executa workflow salvo (nome, parâmetros)
- `automation_create` - Cria workflow (nome, descrição, steps[])
- `automation_list` - Lista workflows disponíveis
- `automation_delete` - Remove workflow
- `task_plan` - Planeja tarefa complexa (goal → steps[])
- `task_execute` - Executa plano passo a passo com checkpoints

## Tipos de Automação
1. **Workflows salvos** - Sequências fixas (ex: "relatório semanal")
2. **Planejamento dinâmico** - Goal → LLM planeja → executa com supervisão
3. **Triggers** - (futuro) Baseado em tempo/evento

## Workflow Steps
```yaml
- id: step_1
  tool: gmail_search
  params: {query: "from:chefes assunto:relatório"}
  output: emails
- id: step_2
  tool: web_search
  params: {query: "tendências mercado {emails[0].topic}"}
  output: research
- id: step_3
  tool: notes_save
  params: {title: "Relatório {date}", content: "{research}", tags: ["#relatório"]}
```

## Regras
- **Sempre mostre o plano** antes de executar tarefas complexas
- Peça confirmação em steps destrutivos (enviar, excluir, publicar)
- Checkpoints: permita usuário revisar entre steps críticos
- Salve workflows repetitivos para reuso
- Log de execução para debug

## Exemplos
- "crie relatório semanal de vendas" → planeja: busca e-mails → busca web → compila → salva nota → envia e-mail
- "automatize: toda segunda, resuma e-mails não lidos e me mande no Telegram" → automation_create
- "execute workflow 'relatório-semanal'" → automation_run