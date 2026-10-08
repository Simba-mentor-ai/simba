#!/bin/bash

# SIMBA Production Deploy Script
# Production deployment script for SIMBA project

set -e  

echo "🚀 Starting SIMBA production deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME="simba-2025"
BACKUP_DIR="./backups"
LOG_FILE="./logs/deploy.log"

mkdir -p logs backups

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
    log "STEP: $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS: $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    log "WARNING: $1"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    log "ERROR: $1"
}

print_step "Running pre-deployment checks..."

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not available"
    exit 1
fi

print_success "Docker and Docker Compose are available"

# Production configuration
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"
HOST_CHECK="simba-refact.irit.fr"

print_step "Deploying to production environment"

if [ ! -f $COMPOSE_FILE ]; then
    print_error "Compose file $COMPOSE_FILE not found"
    exit 1
fi

if [ ! -f $ENV_FILE ]; then
    print_error "$ENV_FILE not found. Please create it with production settings."
    print_error "Required variables: DEBUG=False, ALLOWED_HOSTS=simba-refact.irit.fr, SECRET_KEY=..."
    exit 1
fi

# entrypoint.sh creates the admin and student accounts from these settings and refuses missing or
# weak ones (same rules as here). Check now, while the current version is still running, so a
# deploy never ends with no admin account. Values are never printed or logged.
print_step "Checking the admin and student account settings in $ENV_FILE..."
env_value() {
    grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r' | sed -e "s/^['\"]//" -e "s/['\"]$//"
}
ACCOUNT_ERRORS=0
for PREFIX in SIMBA_ADMIN SIMBA_STUDENT; do
    ACCOUNT_USERNAME=$(env_value "${PREFIX}_USERNAME")
    ACCOUNT_EMAIL=$(env_value "${PREFIX}_EMAIL")
    ACCOUNT_PASSWORD=$(env_value "${PREFIX}_PASSWORD")
    if [ -z "$ACCOUNT_USERNAME" ] || [ -z "$ACCOUNT_EMAIL" ] || [ -z "$ACCOUNT_PASSWORD" ]; then
        print_error "${PREFIX}_USERNAME, ${PREFIX}_EMAIL and ${PREFIX}_PASSWORD must all be set in $ENV_FILE"
        ACCOUNT_ERRORS=1
    elif [[ "$ACCOUNT_EMAIL" != *@* ]]; then
        print_error "${PREFIX}_EMAIL is not an email address"
        ACCOUNT_ERRORS=1
    elif [ ${#ACCOUNT_PASSWORD} -lt 12 ] || [ "${ACCOUNT_PASSWORD,,}" = "${ACCOUNT_USERNAME,,}" ]; then
        print_error "${PREFIX}_PASSWORD is too weak (under 12 characters or same as the username)"
        ACCOUNT_ERRORS=1
    fi
done
unset ACCOUNT_PASSWORD
if [ $ACCOUNT_ERRORS -ne 0 ]; then
    print_error "Nothing was stopped, the site still runs the current version. Fix $ENV_FILE (see README, Production Environment Variables) and run deploy.sh again."
    exit 1
fi
print_success "Admin and student account settings are present"

print_step "Creating database backup (if exists)..."
if docker ps | grep -q "simba.*db"; then
    ./scripts/backup.sh || print_warning "Backup failed or no existing database"
else
    print_step "No existing database found, skipping backup"
fi

print_step "Stopping all containers (preserving database volume)..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE stop || true
print_success "All containers stopped, database volume preserved"

print_step "Removing containers and clearing web volume to ensure fresh deployment..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE rm -f web chainlit || true

# Remove only the web volume to clear old application files, but preserve db volume
print_step "Removing web volume to ensure template changes are applied..."
docker volume rm "${PWD##*/}_web" 2>/dev/null || print_warning "Web volume not found or already removed"

print_step "Pulling latest base images..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE pull || print_warning "Some images may need to be built locally"

print_step "Building containers with no cache to ensure all changes are included..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE build --no-cache web chainlit

print_step "Starting containers..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE up -d

print_step "Waiting for services to be ready..."
sleep 15

print_step "Running database migrations..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python manage.py migrate

print_step "Setting all users as email verified for production..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
import django
django.setup()
from django.utils import timezone
from simbaapp.models import User

# Mark all users as email verified
users_updated = User.objects.filter(is_email_verified=False).update(
    is_email_verified=True,
    email_verified_at=timezone.now()
)

print(f'✅ Marked {users_updated} users as email verified')

# Show user status
total_users = User.objects.count()
verified_users = User.objects.filter(is_email_verified=True).count()
print(f'📊 Total users: {total_users}, Verified: {verified_users}')
"

print_step "Compiling translation messages..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python manage.py compilemessages
print_success "Translation messages compiled"

print_step "Collecting static files..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python manage.py collectstatic --noinput
print_success "Static files collected"

print_step "Clearing Django template cache (if any)..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
import django
django.setup()
from django.core.cache import cache
cache.clear()
print('✅ Django cache cleared')
" || print_warning "Cache clearing failed (cache might not be configured)"

# Health check
print_step "Performing health check..."
if curl -f http://localhost:8000 > /dev/null 2>&1; then
    print_success "Application is responding on port 8000 (nginx proxy)"
else
    print_warning "Application might not be ready yet. Check logs: ENVIRONMENT=production docker compose -f $COMPOSE_FILE logs"
fi

# Show running containers
print_step "Deployment status:"
ENVIRONMENT=production docker compose -f $COMPOSE_FILE ps

# Show version information
if [ -f version.py ]; then
    VERSION=$(python3 -c "import sys; sys.path.append('.'); from version import get_version; print(get_version())" 2>/dev/null || echo "unknown")
    print_success "SIMBA v$VERSION deployed successfully to production!"
else
    print_success "SIMBA deployed successfully to production!"
fi

# Show useful commands
echo ""
echo -e "${BLUE}📝 Useful commands:${NC}"
echo "  • View logs: ENVIRONMENT=production docker compose -f $COMPOSE_FILE logs -f"
echo "  • Stop application: ENVIRONMENT=production docker compose -f $COMPOSE_FILE down"
echo "  • Restart application: ENVIRONMENT=production docker compose -f $COMPOSE_FILE restart"
echo "  • Access shell: ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec web bash"
echo "  • View database: ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec db psql -U simba_user -d simba_db"

echo ""
echo -e "${YELLOW}🔗 Production URLs:${NC}"
echo "  • Main application: https://simba-refact.irit.fr"
echo "  • Chainlit: https://simba-refact.irit.fr/chainlit/"
echo ""

echo ""
echo -e "${YELLOW}🔧 Environment Variables:${NC}"
echo "  • ENVIRONMENT=production"
echo "  • SIMBA_API_URL_PROD=https://simba-refact.irit.fr/api"
echo "  • CHAINLIT_URL_PROD=https://simba-refact.irit.fr/chainlit"
echo ""

log "Production deployment completed successfully" 