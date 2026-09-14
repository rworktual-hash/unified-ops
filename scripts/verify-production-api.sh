#!/bin/bash
# Run on nlp-sm — checks nginx → uvicorn for Unified Ops.
set -euo pipefail
BASE="${1:-https://observability.worktual.tech}"

echo "=== local uvicorn ==="
curl -sf http://127.0.0.1:8000/health
echo ""
curl -s -o /dev/null -w "GET /servers -> %{http_code}\n" http://127.0.0.1:8000/servers

echo "=== via nginx ($BASE) ==="
HEALTH=$(curl -sS "$BASE/health" || true)
echo "/health body: $HEALTH"
if echo "$HEALTH" | grep -q '"status"'; then
  echo "OK: /health is JSON"
else
  echo "FAIL: /health is not JSON (nginx likely serving SPA index.html)"
  exit 1
fi
curl -s -o /dev/null -w "GET /servers -> %{http_code}\n" "$BASE/servers"
curl -sI "$BASE/servers" | head -3

echo "=== nginx /servers location (must be ^~ /servers { without trailing slash) ==="
grep 'location.*servers' /etc/nginx/sites-available/unified-ops || true
