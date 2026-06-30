#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
EXTRA_ROOT="$(pwd)"
PARENT_ROOT="$(cd "$EXTRA_ROOT/.." && pwd)"
[ -f "$PARENT_ROOT/.env" ] && { set -a; source "$PARENT_ROOT/.env"; set +a; }
[ -f "$EXTRA_ROOT/.env" ] && { set -a; source "$EXTRA_ROOT/.env"; set +a; }
if [ ! -d .venv ]; then
  echo "venv not found — run ./scripts/manual/start_orchestrator.sh first."
  exit 1
fi
source .venv/bin/activate
export PYTHONPATH="${PWD}:${PYTHONPATH:-}"
provider="${LLM_PROVIDER:-anthropic}"
if [ "$provider" != "anthropic" ] && [ "$provider" != "openai" ]; then
  echo "Unsupported LLM_PROVIDER: $provider. Supported providers: anthropic, openai."
  exit 1
fi
if [ "$provider" = "anthropic" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY is not set."
  exit 1
fi
if [ "$provider" = "openai" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY is not set."
  exit 1
fi
TOPIC="${*:-Acme Corp, a mid-size industrial robotics manufacturer}"
python -m simulators.manual.orchestrator.hub "$TOPIC"
