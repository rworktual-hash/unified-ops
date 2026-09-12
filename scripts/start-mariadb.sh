#!/usr/bin/env bash
# Starts Unified Ops MariaDB without docker-compose (works when compose v1 breaks on urllib3 2.x).
set -euo pipefail

NAME=unified-ops-mariadb
PORT=3307

if docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "$NAME is already running (host port $PORT)."
  exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "Starting existing container $NAME..."
  docker start "$NAME"
  exit 0
fi

echo "Creating $NAME on host port $PORT..."
docker run -d --name "$NAME" \
  -e MARIADB_ROOT_PASSWORD=root_dev_only \
  -e MARIADB_DATABASE=unified_ops \
  -e MARIADB_USER=unified_ops \
  -e MARIADB_PASSWORD=unified_ops_dev \
  -p "${PORT}:3306" \
  mariadb:11

echo "Done. DATABASE_URL=mysql+pymysql://unified_ops:unified_ops_dev@127.0.0.1:${PORT}/unified_ops"
