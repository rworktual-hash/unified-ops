#!/usr/bin/env bash
# Start Celery worker + beat for scheduled fleet metrics on nlp-sm.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
source .venv/bin/activate

if ! redis-cli ping >/dev/null 2>&1; then
  echo "Redis not reachable (redis-cli ping). Install/start redis or fix REDIS_URL."
  exit 1
fi

pkill -f "celery -A app.celery_app:celery_app worker" 2>/dev/null || true
pkill -f "celery -A app.celery_app:celery_app beat" 2>/dev/null || true
sleep 1

nohup celery -A app.celery_app:celery_app worker --loglevel=info \
  >> /var/log/unified-ops-celery-worker.log 2>&1 &
nohup celery -A app.celery_app:celery_app beat --loglevel=info \
  >> /var/log/unified-ops-celery-beat.log 2>&1 &

echo "Celery worker + beat started. Logs: /var/log/unified-ops-celery-worker.log, ...-beat.log"
echo "Ensure METRICS_SCHEDULED_COLLECT_ENABLED=true in .env and restart beat after env changes."
