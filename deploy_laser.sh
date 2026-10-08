#!/usr/bin/env bash
# ==============================================================================
# SIMBA — Script de déploiement pour la VM LASER (IRIT)
# ==============================================================================
# Remplace deploy.sh pour ce contexte précis : Apache déjà présent sur la VM
# (utilisé comme reverse proxy + terminaison SSL devant les conteneurs Docker),
# domaine déjà configuré : https://simba-dashboard.irit.fr
#
# Usage :
#   sudo ./deploy_laser.sh              # déploiement complet (1re fois ou mise à jour)
#   sudo ./deploy_laser.sh --no-build   # redéploie sans reconstruire les images
#   sudo ./deploy_laser.sh --migrate-only   # ne fait que les migrations Django
#
# Prérequis avant de lancer ce script (voir le guide DEPLOIEMENT_SIMBA_LASER_VM.md) :
#   - Docker + Docker Compose installés
#   - Le fichier .env est déjà rempli à la racine du projet
#   - Apache est configuré avec le vhost simba-dashboard.conf et le certificat SSL
#     Let's Encrypt est déjà obtenu (voir étape dédiée du guide)
# ==============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

LOG_FILE="$PROJECT_DIR/logs/deploy_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

fail() {
    log "ERREUR : $*"
    exit 1
}

NO_BUILD=false
MIGRATE_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --no-build) NO_BUILD=true ;;
        --migrate-only) MIGRATE_ONLY=true ;;
        *) fail "Argument inconnu : $arg (options valides : --no-build, --migrate-only)" ;;
    esac
done

# ── 0. Vérifications préalables ──────────────────────────────────────────────
log "=== Déploiement SIMBA — début ==="

[ -f "$PROJECT_DIR/.env" ] || fail ".env introuvable à la racine du projet. Crée-le avant de relancer (voir le guide)."
command -v docker >/dev/null 2>&1 || fail "docker n'est pas installé."
docker compose version >/dev/null 2>&1 || fail "le plugin 'docker compose' n'est pas installé."

# Le disque de cette VM est serré (/var avait ~3.8G libres à l'installation) —
# Docker stocke ses images/volumes sous /var/lib/docker par défaut, donc on
# vérifie qu'il reste de la marge avant de lancer un build qui pourrait le remplir.
AVAILABLE_VAR_GB=$(df --output=avail -BG /var | tail -1 | tr -dc '0-9')
if [ "${AVAILABLE_VAR_GB:-0}" -lt 2 ]; then
    fail "Moins de 2 Go disponibles sur /var (trouvé: ${AVAILABLE_VAR_GB}G). Libère de l'espace (docker system prune) avant de continuer."
elif [ "${AVAILABLE_VAR_GB:-0}" -lt 4 ]; then
    log "Attention : seulement ${AVAILABLE_VAR_GB}G disponibles sur /var — surveille l'espace pendant le build."
fi

if [ "$MIGRATE_ONLY" = true ]; then
    log "Mode --migrate-only : application des migrations uniquement."
    docker compose exec -T web python manage.py migrate --noinput | tee -a "$LOG_FILE"
    log "=== Migrations appliquées. Fin. ==="
    exit 0
fi

# ── 1. Sauvegarde de la base avant toute mise à jour ─────────────────────────
if docker compose ps db 2>/dev/null | grep -q "Up"; then
    log "Sauvegarde de la base de données avant mise à jour..."
    mkdir -p "$PROJECT_DIR/backups"
    BACKUP_FILE="$PROJECT_DIR/backups/pre_deploy_$(date +%Y%m%d_%H%M%S).sql.gz"
    if docker compose exec -T db pg_dump -U "$(grep '^POSTGRES_USER=' .env | cut -d= -f2)" \
        "$(grep '^POSTGRES_DB=' .env | cut -d= -f2)" | gzip > "$BACKUP_FILE"; then
        log "Sauvegarde écrite dans $BACKUP_FILE"
    else
        log "Attention : la sauvegarde a échoué (base peut-être vide/première installation) — on continue."
    fi
else
    log "Pas de conteneur 'db' déjà actif — première installation, pas de sauvegarde à faire."
fi

# ── 2. Construction et démarrage des conteneurs ──────────────────────────────
if [ "$NO_BUILD" = true ]; then
    log "Démarrage des conteneurs (sans reconstruction des images)..."
    docker compose up -d | tee -a "$LOG_FILE"
else
    log "Construction des images Docker..."
    docker compose build | tee -a "$LOG_FILE"
    log "Démarrage des conteneurs..."
    docker compose up -d | tee -a "$LOG_FILE"
fi

# ── 3. Attente que la base de données soit prête ─────────────────────────────
log "Attente que la base de données réponde..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until docker compose exec -T db pg_isready -U "$(grep '^POSTGRES_USER=' .env | cut -d= -f2)" >/dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        fail "La base de données ne répond toujours pas après ${MAX_ATTEMPTS}s. Vérifie 'docker compose logs db'."
    fi
    sleep 1
done
log "Base de données prête."

# ── 4. Migrations Django ─────────────────────────────────────────────────────
log "Application des migrations Django..."
docker compose exec -T web python manage.py migrate --noinput | tee -a "$LOG_FILE"

# ── 5. Fichiers statiques ────────────────────────────────────────────────────
log "Collecte des fichiers statiques..."
docker compose exec -T web python manage.py collectstatic --noinput | tee -a "$LOG_FILE"

# ── 6. Vérification que tous les services sont bien "Up" ────────────────────
log "État des conteneurs :"
docker compose ps | tee -a "$LOG_FILE"

if docker compose ps | grep -E "web|chainlit|db" | grep -qv "Up"; then
    fail "Au moins un conteneur n'est pas 'Up' — regarde les logs ci-dessus et 'docker compose logs'."
fi

# ── 7. Rechargement du serveur web (si le vhost/certificat a changé) ────────
# Sur la VM LASER, c'est Nginx qui écoute sur 80/443 (pas Apache, même si Apache
# est installé) — on recharge donc Nginx en priorité.
if systemctl is-active --quiet nginx 2>/dev/null; then
    log "Rechargement de Nginx..."
    nginx -t && systemctl reload nginx
elif systemctl is-active --quiet apache2 2>/dev/null; then
    log "Rechargement d'Apache..."
    apache2ctl configtest && systemctl reload apache2
else
    log "Ni Nginx ni Apache ne semblent actifs — vérifie manuellement la configuration du reverse proxy."
fi

log "=== Déploiement terminé avec succès ==="
log "Vérifie : https://simba-dashboard.irit.fr et https://simba-dashboard.irit.fr/chainlit/"
log "Journal complet : $LOG_FILE"
