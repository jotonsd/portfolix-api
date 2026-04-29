# Portfolix API

## Requirements

- Python 3.11+
- PostgreSQL
- Redis

## Installation

```bash
git clone <repo-url>
cd portfolix-api

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
DEBUG=True
SECRET_KEY=your-django-secret-key

DB_NAME=portfolix_db
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

AI_PROVIDER=gemini

REDIS_URL=redis://localhost:6379/0
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

## Database

```bash
createdb portfolix_db
python manage.py migrate
```

## Run

```bash
chmod +x start.sh
./start.sh
```
