#!/bin/sh
set -e

echo "[INIT] Initializing database and knowledge base..."
python -c "from database import init_db; init_db()"

echo "[INIT] Starting FastAPI Web Dashboard on port 8000..."
uvicorn server:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

echo "[INIT] Starting LiveKit Real-Time Voice Agent Worker..."
python agent.py start &
AGENT_PID=$!

trap 'echo "[SHUTDOWN] Terminating processes..."; kill -TERM $SERVER_PID $AGENT_PID 2>/dev/null; wait' SIGTERM SIGINT

# Wait for any process to exit
wait -n $SERVER_PID $AGENT_PID
EXIT_CODE=$?

echo "[SHUTDOWN] Process exited with code $EXIT_CODE. Stopping container."
kill -TERM $SERVER_PID $AGENT_PID 2>/dev/null || true
exit $EXIT_CODE
