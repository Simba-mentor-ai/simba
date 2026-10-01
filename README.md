# SIMBA: The AI That Makes Students Think

SIMBA is a web-based educational platform that empowers teachers to design, deploy, and analyze pedagogically-grounded chatbots powered by large language models. While generative AI is becoming increasingly available, educators often lack the tools to transform it into purposeful, trackable, and effective learning experiences. SIMBA was co-developed with instructors to fill this gap and meet real classroom needs, aligning LLMs with structured teaching practices that support students' development of critical thinking and self-reflection through guided dialogue and actionable insights.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Docker Development Setup](#docker-development-setup)
- [Available Commands](#available-commands)
- [Database Migrations](#database-migrations)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Scripts](#scripts)
- [Production Deployment](#production-deployment)
- [Backup and Restore](#backup-and-restore)
- [Contributing](#contributing)
- [License](#license)

## Prerequisites

- **Python**: 3.13.2
- **Docker**: Latest version
- **Docker Compose**: Latest version
- **PostgreSQL**: 16 (handled by Docker)
- **Node.js**: For any frontend dependencies (if applicable)

## Local Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd simba-2025
```

### 2. Create Virtual Environment

```bash
# Create virtual environment with Python 3.13.2
python3.13 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 3. Install Requirements

```bash
# Upgrade pip
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the root directory with the following variables:

```bash
# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,db

# Database settings
POSTGRES_DB=simba_db
POSTGRES_USER=simba_user
POSTGRES_PASSWORD=secretpassword
DB_HOST=localhost
DB_PORT=5433

# Environment
ENVIRONMENT=development
BASE_URL=http://localhost:8000

# Email settings (optional for development)
EMAIL=your-email@example.com
EMAILAPPPWD=your-app-password

# API URLs
SIMBA_API_URL=http://localhost:8000/api
CHAINLIT_URL=http://localhost:8500
OPENAI_API_KEY=openai_api_key
# Production URLs (for production deployment)
SIMBA_API_URL_PROD=https://your-domain.com/api
CHAINLIT_URL_PROD=https://your-domain.com/chainlit
```

### 5. Local Database Setup (Optional)

If you prefer to use a local PostgreSQL instance instead of Docker:

```bash
# Install PostgreSQL locally and create database
createdb simba_db
```

### 6. Run Migrations

```bash
# Apply database migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
# Start Django development server
python manage.py runserver 8000

# In another terminal, start Chainlit server
chainlit run chainlit_app.py --host 0.0.0.0 --port 8500
```

## Docker Development Setup

For a complete containerized development environment:

### 1. Quick Start

```bash
# Make the development script executable
chmod +x dev.sh

# Start development environment
./dev.sh
```

### 2. Manual Docker Setup

```bash
# Build and start all services
docker compose up --build -d

# View logs
docker compose logs -f

# Stop services
docker compose down -v
```

## Available Commands

### Make Commands

```bash
# Start all services
make up

# Stop all services
make down

# Restart web service
make restart

# View all logs
make logs

# View web service logs
make logs-web

# View Chainlit logs
make logs-chainlit

# View database logs
make logs-db

# Check service status
make status

# Rebuild all services
make rebuild

# Clean up containers and volumes
make clean

# Access web service shell
make shell-web

# Access Chainlit service shell
make shell-chainlit

# Test web service
make test-web

# Test Chainlit service
make test-chainlit
```

### Django Management Commands

```bash
# Run migrations
python manage.py migrate

# Create migrations
python manage.py makemigrations

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run development server
python manage.py runserver

# Open Django shell
python manage.py shell

# Run tests
python manage.py test
```

### Development Scripts

```bash
# Start development environment
./dev.sh

# Deploy to production
./deploy.sh

# Backup database
./scripts/backup.sh

# Restore database
./scripts/restore.sh [backup_file]

# Setup cron backup
./scripts/cron_backup.sh
```

## Database Migrations

### Creating Migrations

When you modify models in `simbaapp/models.py`:

```bash
# Create migration files
python manage.py makemigrations simbaapp

# Apply migrations
python manage.py migrate
```

### Migration in Docker

```bash
# Create migrations in Docker container
docker compose exec web python manage.py makemigrations

# Apply migrations in Docker container
docker compose exec web python manage.py migrate
```

### Migration Best Practices

1. Always create migrations after model changes
2. Review migration files before applying
3. Test migrations on a copy of production data
4. Backup database before applying migrations in production
5. Use `--dry-run` flag to preview migration effects

```bash
# Preview migration without applying
python manage.py migrate --dry-run

# Show migration status
python manage.py showmigrations
```

## Environment Variables

### Required Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SECRET_KEY` | Django secret key | None | `django-insecure-xyz...` |
| `POSTGRES_DB` | Database name | `simba_db` | `simba_db` |
| `POSTGRES_USER` | Database user | `simba_user` | `simba_user` |
| `POSTGRES_PASSWORD` | Database password | `secretpassword` | `your-secure-password` |

### Optional Variables (Needed for production version)

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DEBUG` | Django debug mode | `True` | `False` |
| `ALLOWED_HOSTS` | Allowed host names | `db` | `localhost,yourdomain.com` |
| `EMAIL` | SMTP email address | None | `your-email@gmail.com` |
| `EMAILAPPPWD` | Email app password | None | `your-app-password` |
| `BASE_URL` | Base URL for the application | Depends on environment | `https://yourdomain.com` |

## Project Structure

```
simba-2025/
├── simba/                  # Django project settings
│   ├── settings.py         # Main settings file
│   ├── urls.py            # URL routing
│   └── wsgi.py            # WSGI configuration
├── simbaapp/              # Main Django application
│   ├── models.py          # Database models
│   ├── views.py           # View functions
│   ├── api.py             # API endpoints
│   ├── schemas.py         # API schemas
│   ├── templates/         # HTML templates
│   ├── static/            # Static files (CSS, JS, images)
│   └── migrations/        # Database migrations
├── scripts/               # Utility scripts
│   ├── backup.sh          # Database backup script
│   ├── restore.sh         # Database restore script
│   └── cron_backup.sh     # Automated backup setup
├── public/                # Public assets
├── chainlit_app.py        # Chainlit application
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker services configuration
├── Dockerfile             # Docker image definition
├── dev.sh                 # Development setup script
├── deploy.sh              # Production deployment script
├── Makefile              # Make commands
└── README.md             # This file
```

## Scripts

### Development Scripts

- **`dev.sh`**: Complete development environment setup
- **`entrypoint.sh`**: Docker container entry point with service initialization

### Database Scripts

- **`scripts/backup.sh`**: Create database backups with timestamp
- **`scripts/restore.sh`**: Restore database from backup file
- **`scripts/cron_backup.sh`**: Setup automated daily backups

### Monitoring Scripts

- **`scripts/disk_report.sh`**: Daily disk-space check, run from root's crontab. Emails a full report (who uses the space, upcoming backups, software updates and deploys, growth trend) only when a disk is at or over 80% (critical from 90%); the forecasts are in the report but never send an email on their own. Recipients and thresholds are set at the top of the script; `sudo ./scripts/disk_report.sh --print` shows the report without sending it.

### Deployment Scripts

- **`deploy.sh`**: Production deployment with SSL and domain configuration

## Production Deployment

### 1. Server Setup

```bash
# Clone repository on production server
git clone <repository-url>
cd simba-2025

# Make deployment script executable
chmod +x deploy.sh

# Run deployment script
./deploy.sh
```

### 2. Production Environment Variables

Update your production `.env` file:

```bash
DEBUG=False
ENVIRONMENT=production
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
BASE_URL=https://yourdomain.com
SIMBA_API_URL_PROD=https://yourdomain.com/api
CHAINLIT_URL_PROD=https://yourdomain.com/chainlit

# Default accounts, required in production (deploy.sh stops before touching the site if
# they are missing). Passwords: at least 12 characters, not the same as the username.
# Applied on every start: change a value here, then redeploy or recreate the web container.
# Put a value in single quotes if it contains a $ sign.
SIMBA_ADMIN_USERNAME=your-admin-name
SIMBA_ADMIN_EMAIL=admin@yourdomain.com
SIMBA_ADMIN_PASSWORD=a-long-random-password
SIMBA_STUDENT_USERNAME=your-demo-student
SIMBA_STUDENT_EMAIL=student@yourdomain.com
SIMBA_STUDENT_PASSWORD=another-long-random-password
```

In development these accounts default to `prof`/`prof` and `student`/`student`. In production
there is no default, and any old `prof` or `student` account that still has its default
password is locked on start.

### 3. SSL Configuration

The deployment script automatically configures SSL certificates using Let's Encrypt.

## Backup and Restore

### Manual Backup

```bash
# Create backup
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh backups/backup_YYYYMMDD_HHMMSS.sql
```

### Automated Backups

```bash
# Setup daily automated backups
./scripts/cron_backup.sh
```

### Docker Backup

```bash
# Backup in Docker environment
docker compose exec db pg_dump -U simba_user simba_db > backup.sql

# Restore in Docker environment
docker compose exec -T db psql -U simba_user simba_db < backup.sql
```

## API Endpoints

The application provides RESTful API endpoints:

- **Base URL**: `http://localhost:8000/api` (development)
- **Documentation**: Available at `/api/docs` (Swagger UI)
- **Authentication**: JWT-based authentication
- **Chatbot Interface**: Available at `http://localhost:8500` (Chainlit)

## Features

### For Educators

- **Chatbot Design**: Create pedagogically-grounded chatbots
- **Deployment Tools**: Easy deployment and management
- **Analytics Dashboard**: Track student interactions and learning progress
- **Structured Teaching**: Align LLMs with teaching practices

### For Students

- **Interactive Learning**: Engage with AI tutors designed for critical thinking
- **Guided Dialogue**: Structured conversations that promote reflection
- **Progress Tracking**: Monitor learning journey and achievements

### Technical Features

- **LLM Integration**: Support for multiple language models
- **Real-time Chat**: Powered by Chainlit for seamless interaction
- **Data Analytics**: Comprehensive tracking and analysis tools
- **Scalable Architecture**: Docker-based deployment for easy scaling

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines for Python code
- Write tests for new features
- Update documentation for any API changes
- Ensure all tests pass before submitting PR

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

## Support

For questions, issues, or contributions, please:

1. Check the existing issues on GitHub
2. Create a new issue with detailed description
3. Contact the development team

## Acknowledgments

SIMBA was co-developed with instructors to meet real classroom needs and bridge the gap between generative AI capabilities and effective educational practices.
