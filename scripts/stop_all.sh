#!/usr/bin/env bash
# Stop everything this repo can start:
#   - UI backend (uvicorn, port 8000)
#   - UI frontend (vite / npm run dev, port 5173)
#   - manual swarm agents (ports 9001-9003)
#   - manual orchestrator workers (ports 9101-9103)
#   - manual pipeline runners (swarm.swarm / orchestrator.hub)

echo "Stopping all agent-sim processes..."

kill_port() {
    local port="$1"
    local pids=""
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti tcp:"$port" 2>/dev/null)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser -n tcp "$port" 2>/dev/null)
    fi
    if [ -n "$pids" ]; then
        echo "  port $port: killing $pids"
        kill -9 $pids 2>/dev/null || true
    fi
}

kill_pattern() {
    local pattern="$1"
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        echo "  pattern '$pattern': killing $(pgrep -f "$pattern" | tr '\n' ' ')"
        pkill -9 -f "$pattern" 2>/dev/null || true
    fi
}

# UI servers
kill_port 8000
kill_port 5173
kill_pattern "uvicorn app.main:app"
kill_pattern "vite"
kill_pattern "npm run dev"

# Manual simulator agent servers (swarm 9001-9003, orchestrator 9101-9103)
for port in 9001 9002 9003 9101 9102 9103; do
    kill_port "$port"
done

# Manual simulator pipeline runners and agent modules
kill_pattern "simulators.manual.swarm"
kill_pattern "simulators.manual.orchestrator"

echo "Done."
