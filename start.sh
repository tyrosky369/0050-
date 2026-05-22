#!/bin/bash
# 0050 溫度計 — 啟動腳本

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🌡️  啟動 0050 溫度計..."

# 後端
echo "▶  啟動後端 FastAPI (port 8000)..."
cd "$PROJECT_DIR/backend"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 等待後端就緒
sleep 2

# 前端
echo "▶  啟動前端 Vite (port 5173)..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅  服務已啟動"
echo "   前端：http://localhost:5173"
echo "   後端：http://localhost:8000"
echo "   (首次載入需 30~60 秒抓取 TWSE 資料)"
echo ""
echo "按 Ctrl+C 停止所有服務"

# 等待 Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '已停止'; exit 0" SIGINT SIGTERM
wait
