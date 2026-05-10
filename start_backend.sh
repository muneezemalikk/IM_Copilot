#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")/backend"
source venv/bin/activate
echo ""

# Ensure all required dependencies (like PyJWT) are installed
pip install -q -r requirements.txt

# Free up port 8000 if it's already in use
PIDS=$(lsof -t -i:8000)
if [ ! -z "$PIDS" ]; then
  kill -9 $PIDS 2>/dev/null || true
  sleep 1
fi

echo "  Starting IM|Copilot Backend..."
echo "  API:  http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo ""
uvicorn main:app --reload --host 0.0.0.0 --port 8000
