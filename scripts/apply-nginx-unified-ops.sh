#!/bin/bash
# Install repo nginx vhost on nlp-sm (run as root).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/deploy/nginx/unified-ops.conf"
DEST="/etc/nginx/sites-available/unified-ops"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on nlp-sm."
  exit 1
fi
if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC — git pull in $REPO_ROOT first."
  exit 1
fi

cp "$SRC" "$DEST"
ln -sf ../sites-available/unified-ops /etc/nginx/sites-enabled/unified-ops 2>/dev/null || true
nginx -t
systemctl reload nginx
echo "Installed $DEST and reloaded nginx."
