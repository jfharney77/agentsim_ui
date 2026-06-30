#!/bin/bash
# Start the FastAPI backend server

EXTRA_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARENT_ROOT="$(cd "$EXTRA_ROOT/.." && pwd)"

[ -f "$PARENT_ROOT/.env" ] && { set -a; source "$PARENT_ROOT/.env"; set +a; }
[ -f "$EXTRA_ROOT/.env" ] && { set -a; source "$EXTRA_ROOT/.env"; set +a; }
export AGENT_SIM_REPO_ROOT="$EXTRA_ROOT"

cd "$(dirname "$0")/../backend"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Start the backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
