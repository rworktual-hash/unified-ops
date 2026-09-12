#!/usr/bin/env bash
# Create an Ed25519 key pair for Unified Ops (private key stays local; send .pub to server team).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY_DIR="${KEY_DIR:-$ROOT/credentials}"
KEY_NAME="${KEY_NAME:-unified_ops_ed25519}"
mkdir -p "$KEY_DIR"

PRIV="$KEY_DIR/$KEY_NAME"
PUB="$PRIV.pub"

if [[ -f "$PRIV" ]]; then
  echo "Key already exists: $PRIV"
  echo "Public key to send to server team:"
  cat "$PUB"
  exit 0
fi

ssh-keygen -t ed25519 -f "$PRIV" -N "" -C "unified-ops@$(hostname -s 2>/dev/null || echo dev)"
chmod 600 "$PRIV"
echo "Created: $PRIV"
echo ""
echo "Send this public key to server team (GPU port 4204):"
cat "$PUB"
echo ""
echo "Add to backend .env:"
echo "CREDENTIAL_GPU_KEY_1_PATH=$PRIV"
echo "DEFAULT_SSH_PRIVATE_KEY_PATH=$PRIV"
