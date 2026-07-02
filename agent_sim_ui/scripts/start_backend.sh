#!/bin/bash
# Start the FastAPI backend server

EXTRA_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARENT_ROOT="$(cd "$EXTRA_ROOT/.." && pwd)"

[ -f "$PARENT_ROOT/.env" ] && { set -a; source "$PARENT_ROOT/.env"; set +a; }
[ -f "$EXTRA_ROOT/.env" ] && { set -a; source "$EXTRA_ROOT/.env"; set +a; }
export AGENT_SIM_REPO_ROOT="$EXTRA_ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"

# Refuse to double-start if the port is already taken.
if command -v lsof >/dev/null 2>&1 && lsof -ti tcp:"$BACKEND_PORT" >/dev/null 2>&1; then
    echo "Error: port $BACKEND_PORT is already in use (backend already running?)." >&2
    echo "Run ./scripts/stop_both.sh (or stop_all.sh) first." >&2
    exit 1
fi

cd "$(dirname "$0")/../backend"

# Create the virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Install dependencies if missing (covers a half-created venv too)
if ! python -c "import uvicorn, fastapi" >/dev/null 2>&1; then
    pip install -r requirements.txt
fi

# Start the backend server
exec uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload
