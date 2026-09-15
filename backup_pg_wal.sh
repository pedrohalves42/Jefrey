#!/bin/bash
# ==============================================================================
# PostgreSQL WAL Backup Script for Jefrey
# ==============================================================================
# Realiza backup dos arquivos WAL (Write-Ahead Log) do PostgreSQL.
# Essencial para recuperação de desastres e ponto-a-ponto (PITR).
#
# Usado pelo CI/CD pipeline (ci.yml) e operações de produção.
# ==============================================================================

set -e

# Configuration
PG_CONTAINER="jefrey-postgres"  # Docker container name or empty for local
PG_USER="jefrey"
PG_DB="jefrey"
PG_PASSWORD="jefrey"
BACKUP_DIR="./pg_backup_wal"
RETENTION_DAYS=7

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    logger -t pg_wal_backup "$1"
}

log "=== Iniciando backup WAL do PostgreSQL ==="

# Create backup directory
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    log "Diretório de backup criado: $BACKUP_DIR"
fi

# Verify PostgreSQL is running
if [ -n "$PG_CONTAINER" ]; then
    # Docker mode - check if container is running
    if ! docker ps --filter "name=$PG_CONTAINER" --format '{{.Names}}' | grep -q "$PG_CONTAINER"; then
        log "ERRO: Container PostgreSQL $PG_CONTAINER nao esta rodando"
        exit 1
    fi
    log "Container PostgreSQL detectado: $PG_CONTAINER"
fi

# Method 1: pg_waldump + pg_backup (if available)
# Method 2: Copy WAL files directly from PostgreSQL data directory
# Method 3: Use pg_backup (if configuration allows)

log "Coletando informacoes do PostgreSQL..."

# Get PostgreSQL data directory
if [ -n "$PG_CONTAINER" ]; then
    PG_DATA_DIR=$(docker exec "$PG_CONTAINER" pg_config --datadir 2>/dev/null || echo "/var/lib/postgresql/data")
    log "Directorio de dados (container): $PG_DATA_DIR"
else
    PG_DATA_DIR=$(pg_config --datadir 2>/dev/null || echo "/var/lib/postgresql/data")
    log "Directorio de dados (local): $PG_DATA_DIR"
fi

# List WAL files
if [ -n "$PG_CONTAINER" ]; then
    WAL_FILES=$(docker exec "$PG_CONTAINER" find "$PG_DATA_DIR/pg_wal" -type f -name '*.partial' -o -name '*.wal' 2>/dev/null | wc -l)
    log "Arquivos WAL encontrados (container): $WAL_FILES"
    
    # Copy WAL files to backup
    if [ "$WAL_FILES" -gt 0 ]; then
        log "Copiando arquivos WAL para backup..."
        docker exec "$PG_CONTAINER" find "$PG_DATA_DIR/pg_wal" -type f -name '*.wal' -o -name '*.partial' 2>/dev/null | xargs -I {} cp {} "$BACKUP_DIR/" 2>/dev/null || log "Aviso: Nao foi possivel copiar todos os arquivos WAL"
    else
        log "Nenhum arquivo WAL encontrado para backup"
    fi
    
    # Also fetch latest WAL using pg_switchwal
    log "Forcing checkpoint e switch WAL..."
    docker exec "$PG_CONTAINER" pg_switchwal 2>/dev/null || log "Aviso: pg_switchwal falhou ou nao disponivel"
    
else
    # Local mode
    WAL_FILES=$(find "$PG_DATA_DIR/pg_wal" -type f 2>/dev/null | wc -l)
    log "Arquivos WAL encontrados (local): $WAL_FILES"
    
    if [ "$WAL_FILES" -gt 0 ]; then
        cp "$PG_DATA_DIR/pg_wal"/* "$BACKUP_DIR/" 2>/dev/null || log "Aviso: Nao foi possivel copiar todos os arquivos WAL"
    else
        log "Nenhum arquivo WAL encontrado para backup"
    fi
    
    # Force checkpoint
    pg_ctl reload 2>/dev/null || log "Aviso: pg_ctl reload falhou"
fi

# Create backup metadata
BACKUP_TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
METADATA_FILE="$BACKUP_DIR/backup_manifest_${BACKUP_TIMESTAMP}.txt"
log "Criando metadado do backup..."

cat > "$METADATA_FILE" << EOF
PostgreSQL WAL Backup Manifest
============================
Data: $(date '+%Y-%m-%d %H:%M:%S')
Backup Dir: $BACKUP_DIR
Retencao: $RETENTION_DAYS dias
Arquivos WAL: $(ls "$BACKUP_DIR"/*.wal 2>/dev/null | wc -l)
Versao PostgreSQL: $(docker exec "$PG_CONTAINER" pg_config --version 2>/dev/null || pg_config --version 2>/dev/null || echo "desconhecido")
Container: $PG_CONTAINER
EOF

log "Backup WAL concluido:"
log "  - Diretorio: $BACKUP_DIR"
log "  - Manifest: $METADATA_FILE"
log "  - Arquivos: $(ls "$BACKUP_DIR"/*.wal 2>/dev/null | wc -l)"
log "  - Tamanho: $(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "0")"

# Cleanup old backups
if [ "$RETENTION_DAYS" -gt 0 ]; then
    log "Limpando backups antigos (maiores que $RETENTION_DAYS dias)..."
    find "$BACKUP_DIR" -name "backup_manifest_*.txt" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || log "Aviso: Limpeza de antigos backups"
fi

log "=== Backup WAL finalizado ==="
exit 0