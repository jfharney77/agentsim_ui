# Agent Sim UI — Backend

Python + FastAPI backend for the **Agent Sim UI** (`specs/SIM-UI-*`). This
package launches simulators from the parent `simulated_agentic_mesh` repo with N
parallel instances and visualizes per-agent state live.

## Status

Implemented so far:

- **SIM-UI-100** — shared data model (`app/models.py`): the entities and enums
  referenced by every other spec (`Simulator`, `AgentDescriptor`, `LaunchSpec`,
  `LaunchRequest`/`LaunchResponse`, `InstanceDescriptor`, `AgentRuntimeState`,
  `StateChangeEvent`, `RunLog`/`LogLine`, plus the `AgentState` four-state enum
  and `InstanceStatus`).
- **SIM-UI-101** — Simulator & Agent Discovery (`app/discovery/`): scans the
  parent repo's `simulators/` directory, resolves the correct agent roster for
  each of the five known simulators, and exposes a `SimulatorRegistry`.

Not yet implemented (future specs): launcher (102), state tracking (103),
SQLite logging (104), FastAPI routes (105), and the React frontend (106-108).

## Layout

```
agent_sim_ui/backend/
├── app/
│   ├── config.py            # repo-root resolution + settings (env-overridable)
│   ├── models.py            # SIM-UI-100 shared data model (pydantic)
│   └── discovery/
│       ├── resolvers.py     # per-simulator AgentResolver strategies
│       └── registry.py      # SimulatorRegistry (SIM-UI-101)
├── tests/
│   └── test_discovery.py    # covers SCENARIO-101-01 .. 101-07
└── requirements.txt
```

## Configuration

All settings are read from the environment with sensible defaults
(`app/config.py`):

| Env var | Default | Purpose |
| --- | --- | --- |
| `AGENT_SIM_REPO_ROOT` | auto-detected repo root | Where `simulators/` lives |
| `AGENT_SIM_DB_PATH` | `agent_sim_ui/backend/data/agent_sim.db` | SQLite path (SIM-UI-104) |
| `AGENT_SIM_MAX_CONCURRENCY` | `min(32, cpu*4)` | Process pool bound (SIM-UI-102) |

## Quick start

```bash
cd agent_sim_ui/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Discovery smoke test
python -c "from app.discovery.registry import SimulatorRegistry; \
import json; r=SimulatorRegistry(); \
print(json.dumps([s.model_dump() for s in r.list_all()], indent=2, default=str))"
```

## Tests

```bash
cd agent_sim_ui/backend
pytest -q
```
