#!/bin/bash
# Stop both backend and frontend servers

echo "Stopping backend and frontend servers..."

kill_port() {
    local port="$1"
    local pids=""
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti tcp:"$port" 2>/dev/null)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser -n tcp "$port" 2>/dev/null)
    fi
    if [ -n "$pids" ]; then
        echo "Stopping process(es) on port $port: $pids"
        kill -9 $pids
    fi
}

# Stop backend on port 8000
kill_port 8000

# Kill uvicorn (backend)
pkill -f "uvicorn app.main:app" || echo "Backend uvicorn not running"

# Kill vite dev server (frontend)
pkill -f "vite" || echo "Frontend not running"

# Also kill npm processes that might be running the dev server
pkill -f "npm run dev" || echo "No npm dev processes found"

# Stop manual simulator agent servers (swarm: 9001-9003, orchestrator: 9101-9103)
for port in 9001 9002 9003 9101 9102 9103; do
    kill_port "$port"
done

echo "Servers stopped."
