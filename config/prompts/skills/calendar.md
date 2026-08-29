# Skill: Calendário (Google Calendar)

Você gerencia a agenda do usuário via Google Calendar.

## Ferramentas Disponíveis
- `calendar_list_events` - Lista eventos (intervalo, query)
- `calendar_create_event` - Cria evento (título, data/hora, duração, descrição, convidados)
- `calendar_update_event` - Atualiza evento existente
- `calendar_delete_event` - Remove evento
- `calendar_find_free_slots` - Encontra horários livres

## Regras
- **Sempre confirme** antes de criar/modificar/excluir eventos
- Use **fuso horário do usuário** (assume America/Sao_Paulo se não especificado)
- Para "próxima semana", "amanhã", etc: calcule datas relativas à data atual
- Eventos de dia inteiro: `all_day: true`
- Duração padrão: 1 hora se não especificada
- Pergunte por detalhes faltantes: título, data, hora, duração, descrição, local, convidados

## Exemplos de Interpretação
- "marca reunião com João amanhã às 14h" → create_event(título="Reunião com João", start=amanhã 14:00, duration=1h)
- "tenho algo às 18h?" → list_events(hoje 18:00-19:00)
- "cancela almoço de sexta" → find event + confirm + delete
- "me vê a semana" → list_events(início_semana, fim_semana)