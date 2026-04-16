#!/bin/bash

# LightClaw 开发环境启动脚本

echo "=========================================="
echo "LightClaw Development Server"
echo "=========================================="

# 获取脚本目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 检查 .env 文件
if [ ! -f "$PROJECT_DIR/backend/.env" ]; then
    echo "Creating .env file..."
    cp "$PROJECT_DIR/backend/.env.example" "$PROJECT_DIR/backend/.env"
    echo "Please edit backend/.env with your LLM API credentials"
fi

# 创建数据目录
mkdir -p "$PROJECT_DIR/data/trajectories"
mkdir -p "$PROJECT_DIR/data/screenshots"
mkdir -p "$PROJECT_DIR/data/datapool"
mkdir -p "$PROJECT_DIR/data/exports"
mkdir -p "$PROJECT_DIR/data/eval"

echo ""
echo "Starting backend..."
cd "$PROJECT_DIR/backend"

# 检查 uv
if command -v uv &> /dev/null; then
    uv run python -m app.main &
else
    echo "uv not found, using python directly"
    python -m app.main &
fi

BACKEND_PID=$!

echo ""
echo "Starting frontend..."
cd "$PROJECT_DIR/frontend"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "LightClaw is running!"
echo "=========================================="
echo ""
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# 等待中断
trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID; exit 0" INT

wait
