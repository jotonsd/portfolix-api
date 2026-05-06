#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/venv"
PYTHON="$VENV/bin/python"
GUNICORN="$VENV/bin/gunicorn"
CELERY="$VENV/bin/celery"
FLOWER_PORT="${FLOWER_PORT:-5555}"
STRIPE_PORT="${STRIPE_PORT:-8000}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${CYAN}[portfolix]${NC} $1"; }
ok()   { echo -e "${GREEN}[  OK  ]${NC} $1"; }
warn() { echo -e "${YELLOW}[ WARN ]${NC} $1"; }
fail() { echo -e "${RED}[ FAIL ]${NC} $1"; exit 1; }

# ── Cleanup on exit ────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    log "Shutting down all services..."
    [ -n "$GUNICORN_PID" ] && kill "$GUNICORN_PID" 2>/dev/null && ok "Gunicorn stopped"
    [ -n "$CELERY_PID" ]   && kill "$CELERY_PID"   2>/dev/null && ok "Celery stopped"
    [ -n "$FLOWER_PID" ]   && kill "$FLOWER_PID"   2>/dev/null && ok "Flower stopped"
    [ -n "$STRIPE_PID" ]   && kill "$STRIPE_PID"   2>/dev/null && ok "Stripe listener stopped"
    ok "All services stopped. Goodbye."
}
trap cleanup EXIT INT TERM

echo ""
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}         Portfolix API — Starting          ${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════${NC}"
echo ""

# ── 1. Virtual environment ─────────────────────────────────────────────────────
log "Checking virtual environment..."
if [ ! -d "$VENV" ]; then
    warn "venv not found — creating..."
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
ok "Virtual environment activated"

# ── 2. Dependencies ────────────────────────────────────────────────────────────
log "Installing dependencies..."
pip install -q -r "$PROJECT_DIR/requirements.txt"
ok "Dependencies ready"

# ── 3. .env check ─────────────────────────────────────────────────────────────
[ ! -f "$PROJECT_DIR/.env" ] && fail ".env file not found. Copy .env.example and fill in your values."
ok ".env file found"

# ── 4. PostgreSQL ──────────────────────────────────────────────────────────────
log "Checking PostgreSQL..."
if ! pg_isready -q 2>/dev/null; then
    warn "PostgreSQL not running — trying to start via Homebrew..."
    brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null || true
    sleep 2
    pg_isready -q 2>/dev/null || fail "PostgreSQL is not running. Start it manually and re-run."
fi
ok "PostgreSQL is running"

# ── 5. Redis ───────────────────────────────────────────────────────────────────
log "Checking Redis..."
if ! redis-cli ping &>/dev/null; then
    warn "Redis not running — trying to start via Homebrew..."
    brew services start redis 2>/dev/null || true
    sleep 2
    redis-cli ping &>/dev/null || fail "Redis is not running. Install it: brew install redis, then re-run."
fi
ok "Redis is running"

# ── 6. Directories ─────────────────────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/media/cvs"
ok "Logs and media directories ready"

# ── 7. Migrations ──────────────────────────────────────────────────────────────
log "Running database migrations..."
cd "$PROJECT_DIR"
$PYTHON manage.py migrate --run-syncdb 2>&1 | grep -E "Apply|OK|No migrations" || true
ok "Migrations applied"

# ── 8. Django system check ─────────────────────────────────────────────────────
log "Running system check..."
$PYTHON manage.py check
ok "System check passed"

# ── 9. Stripe webhook listener ────────────────────────────────────────────────
HOST="${DJANGO_HOST:-0.0.0.0}"
PORT="${DJANGO_PORT:-8000}"

if command -v stripe &>/dev/null; then
    log "Starting Stripe webhook listener → http://localhost:$PORT/api/auth/stripe/webhook/"
    stripe listen \
        --forward-to "http://localhost:$PORT/api/auth/stripe/webhook/" \
        --log-level warn \
        > "$PROJECT_DIR/logs/stripe.log" 2>&1 &
    STRIPE_PID=$!
    sleep 2
    kill -0 "$STRIPE_PID" 2>/dev/null \
        && ok "Stripe listener started (PID $STRIPE_PID)" \
        || warn "Stripe listener failed to start — webhooks will not be forwarded locally"
else
    warn "Stripe CLI not found — skipping webhook listener (install: brew install stripe/stripe-cli/stripe)"
fi

# ── 10. Start Celery worker ────────────────────────────────────────────────────
WORKERS="${GUNICORN_WORKERS:-3}"

log "Starting Celery worker..."
$CELERY -A config worker \
    --loglevel=info \
    --logfile="$PROJECT_DIR/logs/celery.log" \
    --concurrency=2 \
    &
CELERY_PID=$!
sleep 3  # wait for worker to fully connect to Redis before Flower inspects it
kill -0 "$CELERY_PID" 2>/dev/null || fail "Celery worker failed to start. Check logs/celery.log"
ok "Celery worker started (PID $CELERY_PID)"

# ── 10. Start Flower (Celery monitoring UI) ────────────────────────────────────
log "Starting Flower monitoring UI (port $FLOWER_PORT)..."
$CELERY -A config flower \
    --port="$FLOWER_PORT" \
    --logfile="$PROJECT_DIR/logs/flower.log" \
    --logging=error \
    &
FLOWER_PID=$!
sleep 1
ok "Flower started (PID $FLOWER_PID) → http://localhost:$FLOWER_PORT"

# ── 11. Start Gunicorn ─────────────────────────────────────────────────────────
log "Starting Gunicorn ($WORKERS workers)..."
$GUNICORN config.wsgi:application \
    --bind "$HOST:$PORT" \
    --workers "$WORKERS" \
    --timeout 120 \
    --reload \
    --access-logfile "$PROJECT_DIR/logs/access.log" \
    --error-logfile "$PROJECT_DIR/logs/gunicorn_error.log" \
    --log-level info \
    &
GUNICORN_PID=$!
sleep 2
kill -0 "$GUNICORN_PID" 2>/dev/null || fail "Gunicorn failed to start. Check logs/gunicorn_error.log"

echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}   All services running                    ${NC}"
echo -e "${BOLD}${GREEN}                                           ${NC}"
echo -e "${BOLD}${GREEN}   API     → http://localhost:$PORT/api/        ${NC}"
echo -e "${BOLD}${GREEN}   Jobs    → http://localhost:$PORT/api/jobs/   ${NC}"
echo -e "${BOLD}${GREEN}   Monitor → http://localhost:$FLOWER_PORT      ${NC}"
echo -e "${BOLD}${GREEN}   Admin   → http://localhost:$PORT/admin/       ${NC}"
echo -e "${BOLD}${GREEN}   Stripe  → logs/stripe.log                     ${NC}"
echo -e "${BOLD}${GREEN}                                                 ${NC}"
echo -e "${BOLD}${GREEN}   Logs   → logs/                                ${NC}"
echo -e "${BOLD}${GREEN}   Press Ctrl+C to stop everything         ${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════${NC}"
echo ""

# Keep alive — wait for either process to die
wait "$GUNICORN_PID" "$CELERY_PID"
