#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
EXTRA_ROOT="$(pwd)"
PARENT_ROOT="$(cd "$EXTRA_ROOT/.." && pwd)"
[ -f "$PARENT_ROOT/.env" ] && { set -a; source "$PARENT_ROOT/.env"; set +a; }
[ -f "$EXTRA_ROOT/.env" ] && { set -a; source "$EXTRA_ROOT/.env"; set +a; }
if [ ! -d .venv ]; then
  python -m venv .venv
  source .venv/bin/activate
  pip install -r simulators/manual/swarm/requirements.txt
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
resolve_module() {
  local pkg="$1" role="$2" impl="$3"
  case "$impl" in
    a2a) echo "${pkg}.agentic_mesh.${role}.a2a.${role}" ;;
    langgraph) echo "${pkg}.agentic_mesh.${role}.langgraph.${role}" ;;
    degrading-a2a) echo "${pkg}.agentic_mesh.${role}.a2a.degrading_${role}" ;;
    degrading-langgraph) echo "${pkg}.agentic_mesh.${role}.langgraph.degrading_${role}" ;;
    *) echo "Unknown impl '${impl}' for ${role}" >&2; exit 1 ;;
  esac
 }
RESEARCHER_MOD=$(resolve_module simulators.manual.swarm researcher "${RESEARCHER_IMPL:-langgraph}")
ANALYST_MOD=$(resolve_module simulators.manual.swarm analyst "${ANALYST_IMPL:-langgraph}")
WRITER_MOD=$(resolve_module simulators.manual.swarm writer "${WRITER_IMPL:-langgraph}")
base_port="${PORT_BASE:-9001}"
echo "starting swarm agents:"
echo " researcher -> ${RESEARCHER_MOD}"
echo " analyst -> ${ANALYST_MOD}"
echo " writer -> ${WRITER_MOD}"
pids=()
cleanup() { echo; echo "stopping swarm agents..."; kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
python -m "$RESEARCHER_MOD" & pids+=($!)
python -m "$ANALYST_MOD" & pids+=($!)
python -m "$WRITER_MOD" & pids+=($!)
echo "waiting for swarm agents to come online..."
for i in $(seq 1 20); do
  up=0
  for p in "$base_port" "$((base_port + 1))" "$((base_port + 2))"; do
    curl -s -o /dev/null "http://127.0.0.1:$p/.well-known/agent-card.json" && up=$((up+1)) || true
  done
  if [ "$up" -eq 3 ]; then
    echo "all 3 swarm agents up (ports ${base_port}-$((base_port + 2)))"
    echo "run the pipeline: ./scripts/manual/run_swarm.sh \"Acme Corp\""
    break
  fi
  sleep 1
done
wait
