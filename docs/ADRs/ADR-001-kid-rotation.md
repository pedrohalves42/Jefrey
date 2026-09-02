# ADR-001 — HMAC Kid Rotation (EventBus)

**Status**: Accepted — P4-01..03 implementado
**Data**: 2026-09-02
**Decisores**: Maintainer + Security Eng (livro 3 ch.4)
**Relacionado**: CIPHER-033, P4-01/02/03, `src/jefrey/eventbus/signing.py`, `PLANO_FASE_P4_PROD.md`

## Contexto

EventBus original usava `JEFREY_EVENTBUS__HMAC_KEY` unico + `user_id.timestamp.canonical` sem `kid`. Rotacionar chave quebraria assinaturas antigas no Redis Stream (mensagens ja em `jefrey.events.{user_id}.{tool}` e DLQ `jefrey:dlq:{user_id}`).

Requisitos:
- Zero downtime rotation
- Dual-verify durante janela
- Metric sem cardinalidade por user_id (Prometheus Brazil ch.5)
- Fail-closed em prod (sem auto-key)

## Decisao

1. **Novo env**: `JEFREY_EVENTBUS__HMAC_KEYS_JSON='{"v1":"<hex32>","v2":"<hex32>"}'` (dict kid->hex) + `JEFREY_EVENTBUS__HMAC_KID=v1` (kid ativo para sign).
2. **Sign**: `sign_message` inclui `kid` no envelope; HMAC sobre `user_id.timestamp.canonical` (kid seleciona chave, nao entra no HMAC — evita quebra Stream).
3. **Verify**: `verify_message` tenta `kid` da mensagem primeiro; fallback dual-verify v1+v2; legacy v0 (sem kid) verifica com ambas e emite `DeprecationWarning` + inc `jefrey_eventbus_kid_legacy_total` (sem label user_id).
4. **Rollout** (sem quebra):
   - Fase A: deploy dual-verify (aceita v1 e v2), ainda publica v1
   - Fase B: muda `HMAC_KID=v2`, passa a publicar v2 (dual-verify ainda aceita v1)
   - Fase C: apos TTL do Stream (maxlen 10000 ~ dias), remove v1 de `HMAC_KEYS_JSON`, sobra v2
5. **Compat**: `_get_hmac_keys()` suporta ambos: se `HMAC_KEYS_JSON` ausente, usa `HMAC_KEY` legacy como v1.
6. **Metric**: `EVENTBUS_KID_LEGACY_TOTAL` Counter sem labels (cardinalidade baixa).

## Consequencias

- **Positivas**: rotacao sem replay, Streams intactos, metric observavel, fail-closed preservado.
- **Negativas**: leve complexidade dual-verify (2 HMAC por msg legacy durante janela).
- **Riscos**: se ambos v1+v2 vazarem, rotation nao salva — rotacionar tambem via `openssl rand -hex 32` e restart.

## Alternativas consideradas

- Incluir `kid` no HMAC input: rejeitada — quebraria verificação de msgs antigas (input muda).
- `user_id` no payload kid: rejeitada — mesmo problema Stream.

## Links

- `src/jefrey/eventbus/signing.py` (implementacao)
- `src/jefrey/core/metrics.py` (EVENTBUS_KID_LEGACY_TOTAL)
- `THREAT_MODEL.md` 5.1 (controles)
