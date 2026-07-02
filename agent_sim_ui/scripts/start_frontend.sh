#!/bin/bash
# Start the React frontend dev server

EXTRA_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARENT_ROOT="$(cd "$EXTRA_ROOT/.." && pwd)"

[ -f "$PARENT_ROOT/.env" ] && { set -a; source "$PARENT_ROOT/.env"; set +a; }
[ -f "$EXTRA_ROOT/.env" ] && { set -a; source "$EXTRA_ROOT/.env"; set +a; }

FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Refuse to double-start: vite would silently drift to another port,
# breaking the printed URL and the backend CORS allowlist.
if command -v lsof >/dev/null 2>&1 && lsof -ti tcp:"$FRONTEND_PORT" >/dev/null 2>&1; then
    echo "Error: port $FRONTEND_PORT is already in use (frontend already running?)." >&2
    echo "Run ./scripts/stop_both.sh (or stop_all.sh) first." >&2
    exit 1
fi

cd "$(dirname "$0")/../frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    npm install
fi

# Start the frontend dev server (--strictPort: fail loudly rather than
# silently drifting to another port if 5173 is somehow still taken)
exec npm run dev -- --port "$FRONTEND_PORT" --strictPort
