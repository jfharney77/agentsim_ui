#!/bin/bash
# Start both backend and frontend servers

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Stop both children when this script is interrupted or killed.
cleanup() {
    echo
    echo "Stopping servers..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
}
trap cleanup INT TERM

# Start backend in background
echo "Starting backend..."
"$SCRIPT_DIR/start_backend.sh" &
BACKEND_PID=$!

# Wait until the backend answers (up to 30s) instead of a blind sleep.
echo "Waiting for backend on port $BACKEND_PORT..."
for i in $(seq 1 30); do
    if curl -s -o /dev/null "http://localhost:$BACKEND_PORT/api/simulators"; then
        echo "Backend is up: http://localhost:$BACKEND_PORT"
        break
    fi
    # Bail out early if the backend process already died (e.g. port in use).
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "Error: backend failed to start — see output above." >&2
        exit 1
    fi
    if [ "$i" -eq 30 ]; then
        echo "Error: backend did not become ready within 30s." >&2
        cleanup
        exit 1
    fi
    sleep 1
done

# Start frontend in background
echo "Starting frontend..."
"$SCRIPT_DIR/start_frontend.sh" &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID (http://localhost:$BACKEND_PORT)"
echo "Frontend PID: $FRONTEND_PID (http://localhost:$FRONTEND_PORT)"
echo "Both servers started. Ctrl-C or './scripts/stop_both.sh' to stop them."

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
