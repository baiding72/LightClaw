#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/3] Building frontend"
cd "$ROOT_DIR/frontend"
npm run build

echo "[2/3] Starting frontend dev server"
nohup npm run dev -- --host 127.0.0.1 > "$ROOT_DIR/frontend-dev.log" 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo "[3/3] Starting backend API server"
cd "$ROOT_DIR/backend"
nohup uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 > "$ROOT_DIR/backend-dev.log" 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo
echo "Frontend: http://127.0.0.1:5173"
echo "Backend:  http://127.0.0.1:8000"
echo
echo "Logs:"
echo "  $ROOT_DIR/frontend-dev.log"
echo "  $ROOT_DIR/backend-dev.log"
