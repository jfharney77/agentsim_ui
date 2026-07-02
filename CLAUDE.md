# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A standalone web UI for launching **multi-agent simulators** N-times in parallel and visualizing each agent's live state. It wraps five simulators that live under `simulators/` and shows, per instance, a colored circle per agent (not_started/running/completed/errored), streaming logs, and a Context Visualizer of the LLM message history.

This is the de-proprietarized copy of the original framework: only `anthropic` (default) and `openai` LLM providers are supported. See `SUMMARY.md` for the full list of what was removed/preserved. The original spec IDs (`SIM-UI-100` … `SIM-UI-108`) are referenced throughout the backend docstrings and map to components below.

## Repository layout

- `agent_sim_ui/backend/` — Python + FastAPI backend (the orchestration brain).
- `agent_sim_ui/frontend/` — React + Vite + TypeScript + Tailwind UI.
- `agent_sim_ui/scripts/` — start/stop scripts for the UI (backend on `:8000`, frontend on `:5173`).
- `simulators/` — the five simulators the backend launches: `chatdev`, `metagpt`, `hyperagent`, `manual/swarm`, `manual/orchestrator`. Each `manual` agent has both `a2a` and `langgraph` implementations.
- `scripts/manual/` — run the manual swarm/orchestrator simulators directly, without the UI.
- `.env` / `.env.template` — runtime config (LLM provider, API keys, model overrides, `*_IMPL` strategy selectors, `VITE_*` frontend vars).

## Commands

Run the full app (creates venv + npm install on first run):
```bash
cd agent_sim_ui
./scripts/start_both.sh      # backend :8000 + frontend :5173
./scripts/stop_both.sh       # kills :8000, vite, and manual agent ports 9001-9003 / 9101-9103
```

Backend only:
```bash
cd agent_sim_ui/backend
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q                                    # all tests
pytest tests/test_launcher.py -q             # one file
pytest tests/test_api.py::<name> -q          # one test
```

Frontend only:
```bash
cd agent_sim_ui/frontend
npm install
npm run dev        # vite dev server, proxies /api -> localhost:8000
npm run build      # tsc typecheck + vite build
```

Run a manual simulator without the UI (from repo root):
```bash
./scripts/manual/start_swarm.sh && ./scripts/manual/run_swarm.sh "Acme Corp"
./scripts/manual/start_orchestrator.sh && ./scripts/manual/run_orchestrator.sh "Acme Corp"
```

## Backend architecture

A request flows through four components wired together in `app/api.py::create_app` (all are interface-backed and injectable for tests):

1. **Discovery** (`app/discovery/`, SIM-UI-101) — `SimulatorRegistry` scans `simulators/` and resolves each simulator's agent roster via per-simulator `AgentResolver` strategies (`resolvers.py`). A missing directory is skipped; an unparseable known simulator falls back to a hard-coded roster rather than crashing.
2. **Launcher** (`app/launcher/`, SIM-UI-102) — `SimulationLauncher` starts a simulator N times as independent OS processes. Each runs in its own process *session* (`start_new_session=True`) so the whole process group (including agent servers spawned by the manual simulators) can be killed with one `killpg`. A concurrency counter bounds simultaneous instances; excess instances queue in `_pending`. Merged stdout/stderr is read line-by-line and fanned out to **sinks** (`sinks.py`, `CompositeSink`).
3. **Tracking** (`app/tracking/`, SIM-UI-103) — `StateTracker` is a sink that feeds captured output through a per-simulator parser (`parsers.py`) to derive each agent's `AgentState`. Exposes both a poll `snapshot` and a push `subscribe` async stream of `StateChangeEvent`s. It mutates the same `AgentRuntimeState` objects held by the instance descriptors, keeping launcher snapshots and the tracker consistent.
4. **Storage** (`app/storage/`, SIM-UI-104) — `RunStore` is also a sink: it persists run groups, instances, every log line, every state transition, and per-instance summaries to one SQLite file (`AGENT_SIM_DB_PATH`, WAL mode, batched buffered writes so high-volume output never blocks).

`app/models.py` (SIM-UI-100) is the shared pydantic data model used everywhere: `AgentState` (4-state enum: not_started/running/completed/errored), `InstanceStatus`, `LaunchKind` (python/bash), `Simulator`, `LaunchRequest`/`LaunchResponse`, `InstanceDescriptor`, `AgentRuntimeState`, `StateChangeEvent`, `RunLog`.

`app/cv_export.py` writes a Context Visualizer `state.json` (LLM message history) **atomically** (temp file + `os.replace`) so the live watcher polling the file never sees a half-written write. `app/runners/hyperagent_runner.py` is a thin subprocess entrypoint the launcher invokes for the HyperAgent simulator.

Key API routes (all under `/api`): `GET /simulators`, `POST /launch`, `GET /runs/{id}`, `POST /runs/{id}/cancel`, `GET /instances/{id}/log`, `GET /instances/{id}/agents/{aid}/context`, and the SSE stream `GET /runs/{id}/events`. Server-side concurrency is allowlisted (`ALLOWED_CONCURRENCY = {1,2,5,10,100,1000}`) — never trust the client's count.

## Frontend architecture

Three routes (`App.tsx`): `/` (`MainPage` — pick a simulator + count, launch), `/run/:runGroupId` (`RunView` — live view of one run group), `/parallel` (`ParallelPage` — high-fanout 100/1000-instance grid). Components include `AgentCircle` (the colored state dot), `InstancePane`, `LogViewer`, `ContextViewer`, `AggregateStats`. Types mirror the backend model in `src/types/api.ts`. `VITE_MIN_STATE_VISIBLE_MS` enforces a minimum visible duration per state so fast transitions remain perceptible.

## Configuration

Backend settings are env-overridable (`app/config.py`, `get_settings()` is `lru_cache`'d — call `get_settings.cache_clear()` in tests after mutating env):

| Env var | Default | Purpose |
| --- | --- | --- |
| `AGENT_SIM_REPO_ROOT` | auto-detected (walks up for a dir containing `simulators/`) | where `simulators/` lives |
| `AGENT_SIM_DB_PATH` | `backend/data/agent_sim.db` | SQLite path |
| `AGENT_SIM_MAX_CONCURRENCY` | `min(32, cpu*4)` | process-pool bound |
| `AGENT_SIM_CORS_ORIGINS` | `localhost:5173,127.0.0.1:5173` | allowed CORS origins |

The start scripts source `../.env` (parent repo) then the local `.env`, and export `AGENT_SIM_REPO_ROOT` to this repo root. LLM behavior is driven by `LLM_PROVIDER` (`anthropic`/`openai`), `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, optional `SWARM_MODEL`/`ORCHESTRATOR_MODEL`/`HYPERAGENT_MODEL`, and `RESEARCHER_IMPL`/`ANALYST_IMPL`/`WRITER_IMPL` (`langgraph` or `a2a`).

## Known limitation

The manual simulators (swarm/orchestrator) hard-code ports in their Python (swarm 9001-9003, orchestrator 9101-9103) and do **not** respect a per-instance `PORT_BASE`, so parallel manual runs can collide on ports. The other three simulators parallelize cleanly.
