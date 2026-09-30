#!/bin/bash

# SIMBA Database Backup Script
# Creates automated backups of the PostgreSQL database

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths don't depend on the folder the script is started from
# (deploy.sh runs it from the project folder, cron from anywhere)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
# Backups go to /local with the database, not /var; override with BACKUP_DIR=...
BACKUP_DIR="${BACKUP_DIR:-/local/simba/backups}"
LOG_FILE="$BACKUP_DIR/backup.log"
MAX_BACKUPS=30

# Dumps contain user data (emails, password hashes): readable by the owner only
umask 077

mkdir -p "$BACKUP_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
    log "STEP: $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS: $1"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    log "ERROR: $1"
}

print_step "Starting database backup..."

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/simba_backup_$TIMESTAMP.sql"

print_step "Creating database backup..."

# The container is found through docker compose (no hard-coded container name).
# Postgres listens on 5433 (see docker-compose.prod.yml); user and database
# are read from the container's own environment.
if ! docker compose -f "$COMPOSE_FILE" exec -T db \
        sh -c 'pg_dump -p 5433 -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$BACKUP_FILE"; then
    print_error "Database backup failed (is the db container running?)"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# pg_dump writes this line at the end; without it the dump is incomplete
if ! grep -q "PostgreSQL database dump complete" "$BACKUP_FILE"; then
    print_error "Database backup is incomplete: $(basename "$BACKUP_FILE")"
    rm -f "$BACKUP_FILE"
    exit 1
fi

gzip "$BACKUP_FILE"
COMPRESSED_FILE="${BACKUP_FILE}.gz"

FILE_SIZE=$(ls -lh "$COMPRESSED_FILE" | awk '{print $5}')

print_success "Database backup created: $(basename "$COMPRESSED_FILE") ($FILE_SIZE)"

print_step "Cleaning up old backups (keeping last $MAX_BACKUPS)..."

cd "$BACKUP_DIR"
ls -t simba_backup_*.sql.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm

REMAINING_BACKUPS=$(ls simba_backup_*.sql.gz 2>/dev/null | wc -l)
print_success "Cleanup completed. $REMAINING_BACKUPS backups remaining."

ln -sf "$(basename "$COMPRESSED_FILE")" latest_backup.sql.gz

log "Backup completed successfully: $COMPRESSED_FILE"

print_success "Backup process completed successfully!"
