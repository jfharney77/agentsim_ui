#!/bin/bash
# Start the React frontend dev server

EXTRA_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARENT_ROOT="$(cd "$EXTRA_ROOT/.." && pwd)"

[ -f "$PARENT_ROOT/.env" ] && { set -a; source "$PARENT_ROOT/.env"; set +a; }
[ -f "$EXTRA_ROOT/.env" ] && { set -a; source "$EXTRA_ROOT/.env"; set +a; }

cd "$(dirname "$0")/../frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    npm install
fi

# Start the frontend dev server
npm run dev
