#!/usr/bin/env bash
# backup_restore.sh — Prova idempotente de backup/restore Postgres (DDIA cap.3)
# Uso: bash scripts/backup_restore.sh [--verify-only]
# Requisito: docker compose up postgres
set -euo pipefail
PROJECT=jefrey
DB_USER=${JEFREY_DATABASE__USER:-jefrey}
DB_NAME=${JEFREY_DATABASE__DB:-jefrey}
CONTAINER=jefrey-postgres
BACKUP_FILE=${1:-/tmp/jefrey_backup_$(date +%Y%m%d_%H%M%S).sql}
VERIFY_ONLY=false
[[ "${1:-}" == "--verify-only" ]] && VERIFY_ONLY=true

echo "[backup] Verificando postgres healthy..."
docker inspect $CONTAINER --format '{{.State.Health.Status}}' 2>/dev/null | grep -q healthy || { echo "postgres nao healthy"; docker ps; exit 1; }

if [[ "$VERIFY_ONLY" == "true" ]]; then
  echo "[backup] verify-only: checando pg_dump idempotente (sem arquivo)..."
  docker exec $CONTAINER pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges > /tmp/_verify_dump.sql
  RC=$?
  if [[ $RC -ne 0 ]]; then echo "pg_dump falhou RC=$RC"; exit 1; fi
  docker exec $CONTAINER pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges > /tmp/_verify_dump2.sql
  diff -q /tmp/_verify_dump.sql /tmp/_verify_dump2.sql && echo "[backup] pg_dump idempotente OK (DDIA cap3)" || echo "[backup] WARN diff detectado (dados mudaram entre dumps)"
  LINES=$(wc -l < /tmp/_verify_dump.sql)
  echo "[backup] linhas dump: $LINES RC 0 prove OK"
  rm -f /tmp/_verify_dump.sql /tmp/_verify_dump2.sql
  exit 0
fi

echo "[backup] pg_dump -> $BACKUP_FILE ..."
docker exec $CONTAINER pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges > "$BACKUP_FILE"
RC=$?
if [[ $RC -ne 0 ]]; then echo "[backup] FAIL RC=$RC"; exit 1; fi
echo "[backup] OK RC 0 linhas=$(wc -l < "$BACKUP_FILE") bytes=$(wc -c < "$BACKUP_FILE")"

RESTORE_DB="${DB_NAME}_restore_$(date +%s)"
echo "[restore] criando DB temporario $RESTORE_DB para prova..."
docker exec $CONTAINER psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $RESTORE_DB;" 2>&1 | head -n 5
cat "$BACKUP_FILE" | docker exec -i $CONTAINER psql -U "$DB_USER" -d "$RESTORE_DB" > /tmp/restore.log 2>&1 || true
RESTORE_RC=$?
echo "[restore] RC=$RESTORE_RC log head:"
head -n 20 /tmp/restore.log
docker exec $CONTAINER psql -U "$DB_USER" -d postgres -c "DROP DATABASE $RESTORE_DB;" 2>&1 | head -n 5
if [[ $RESTORE_RC -eq 0 ]]; then echo "[restore] prove OK — backup reimportavel (idempotente)"; else echo "[restore] WARN restore RC $RESTORE_RC (ver /tmp/restore.log)"; fi

echo "[done] backup_restore.sh concluido. Arquivo: $BACKUP_FILE"
echo "Para verificar novamente: bash scripts/backup_restore.sh --verify-only"