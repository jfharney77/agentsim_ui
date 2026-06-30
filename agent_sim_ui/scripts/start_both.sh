#!/bin/bash
# Start both backend and frontend servers

SCRIPT_DIR="$(dirname "$0")"

# Start backend in background
echo "Starting backend..."
"$SCRIPT_DIR/start_backend.sh" &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend in background
echo "Starting frontend..."
"$SCRIPT_DIR/start_frontend.sh" &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Both servers started. Run './scripts/stop_both.sh' to stop them."

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
