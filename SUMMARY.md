# Agent Sim UI Extra - Summary

This directory contains a standalone copy of the simulator framework and agent_sim_ui, suitable for standalone use without proprietary dependencies.

## What Was Done

### 1. Proprietary LLM Manager Removal from Simulators

Removed all proprietary code and dependencies from the copied simulators:

**Modified Files (79 Python files validated):**
- `simulators/chatdev/agents/brain.py`
- `simulators/metagpt/brain.py`
- `simulators/manual/swarm/brain.py`
- `simulators/manual/orchestrator/brain.py`
- `simulators/hyperagent/brain.py`
- `simulators/hyperagent/config.py`
- `simulators/hyperagent/runner.py`
- `simulators/hyperagent/test_smoke.py`
- `simulators/chatdev/run_chatdev_sim.py`
- `simulators/metagpt/run_metagpt_sim.py`
- `simulators/chatdev/engine/chat_chain.py`
- `simulators/chatdev/engine/phase.py`
- `simulators/chatdev/engine/role_playing.py`

**Changes:**
- Removed proprietary provider from all brain modules
- Removed `llm_managers` imports and `LLMClients` usage
- Removed proprietary provider functions
- Removed proprietary environment variable references
- Updated HyperAgent to use direct Anthropic/OpenAI LangChain clients
- Updated documentation in README and CHANGELOG files to remove proprietary references

**Supported Providers (after changes):**
- `anthropic` (default)
- `openai`

### 2. Created agent_sim_ui_extra Directory Structure

```
agent_sim_ui_extra/
├── .env                    # Runtime configuration with defaults
├── .env.template           # Template with placeholders
├── agent_sim_ui/           # Copied UI application
├── scripts/
│   └── manual/
│       ├── start_swarm.sh
│       ├── run_swarm.sh
│       ├── start_orchestrator.sh
│       └── run_orchestrator.sh
└── simulators/             # Standalone simulator copies
    ├── chatdev/
    ├── hyperagent/
    ├── manual/
    └── metagpt/
```

### 3. Copied agent_sim_ui Application

Copied the entire `agent_sim_ui` directory to `agent_sim_ui_extra/agent_sim_ui/`.

**Patched Files:**
- `agent_sim_ui/scripts/start_backend.sh`
  - Added env sourcing from parent repo and local .env
  - Exported `AGENT_SIM_REPO_ROOT` to point to agent_sim_ui_extra

- `agent_sim_ui/scripts/start_frontend.sh`
  - Added env sourcing from parent repo and local .env

### 4. Created Manual Simulator Scripts

Created standalone versions of manual simulator scripts in `scripts/manual/`:

**Features:**
- Source environment from parent repo `.env` first, then local `.env`
- Validate LLM provider (only anthropic/openai supported)
- Validate required API keys based on provider
- Removed proprietary auth client installation
- Removed proprietary environment variable checks

**Scripts:**
- `start_swarm.sh` - Start swarm agents on ports 9001-9003
- `run_swarm.sh` - Run swarm pipeline
- `start_orchestrator.sh` - Start orchestrator workers on ports 9101-9103
- `run_orchestrator.sh` - Run orchestrator pipeline

### 5. Created Environment Files

**`.env`** (with runnable defaults):
```env
LLM_PROVIDER=anthropic
RESEARCHER_IMPL=langgraph
ANALYST_IMPL=langgraph
WRITER_IMPL=langgraph
VITE_API_BASE_URL=/api
VITE_MIN_STATE_VISIBLE_MS=1500
AGENT_SIM_MAX_CONCURRENCY=16
```

**`.env.template`** (with placeholders):
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
SWARM_MODEL=
ORCHESTRATOR_MODEL=
HYPERAGENT_MODEL=
RESEARCHER_IMPL=langgraph
ANALYST_IMPL=langgraph
WRITER_IMPL=langgraph
VITE_API_BASE_URL=/api
VITE_MIN_STATE_VISIBLE_MS=1500
AGENT_SIM_MAX_CONCURRENCY=16
```

## How to Use

### Start the UI

```bash
cd agent_sim_ui_extra/agent_sim_ui
./scripts/start_both.sh
```

The UI will be available at:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

### Run Manual Simulators Directly

**Swarm:**
```bash
cd agent_sim_ui_extra
./scripts/manual/start_swarm.sh
./scripts/manual/run_swarm.sh "Acme Corp"
```

**Orchestrator:**
```bash
cd agent_sim_ui_extra
./scripts/manual/start_orchestrator.sh
./scripts/manual/run_orchestrator.sh "Acme Corp"
```

### Environment Configuration

1. Copy `.env.template` to `.env` (if not already present)
2. Fill in your API keys:
   - For Anthropic: `ANTHROPIC_API_KEY`
   - For OpenAI: `OPENAI_API_KEY`
3. Set `LLM_PROVIDER` to `anthropic` or `openai`
4. Optionally set model-specific variables:
   - `SWARM_MODEL`
   - `ORCHESTRATOR_MODEL`
   - `HYPERAGENT_MODEL`

## Important Limitations

### Fixed Ports in Manual Simulators

The manual simulators (swarm/orchestrator) still use fixed ports in the Python code:
- Swarm: 9001-9003
- Orchestrator: 9101-9103

This means parallel manual instances may conflict on ports. The UI backend sets `PORT_BASE` for parallel launches, but the simulator Python modules do not currently respect this environment variable.

To enable full parallel support, the following files would need to be updated:
- `simulators/manual/swarm/swarm.py`
- `simulators/manual/swarm/agentic_mesh/*/a2a/*.py`
- `simulators/manual/swarm/agentic_mesh/*/langgraph/*.py`
- `simulators/manual/orchestrator/hub.py`
- `simulators/manual/orchestrator/agentic_mesh/*/a2a/*.py`
- `simulators/manual/orchestrator/agentic_mesh/*/langgraph/*.py`

## Validation

All changes were validated:
- AST parsing passed for 79 Python files in copied simulators
- Shell syntax validation passed for all new scripts
- Backend repo-root detection correctly resolves to agent_sim_ui_extra
- Backend simulators_dir correctly resolves to agent_sim_ui_extra/simulators

## Differences from Original

### Removed
- All proprietary LLM provider support
- `llm_managers` module dependencies
- Proprietary auth client installation
- Proprietary environment variables (CLIENT_ID, CLIENT_SECRET, OPENAI_API_BASE, MODEL_KEY, DEFAULT_MODEL, USE_SSO)
- Proprietary certificate bundle handling

### Preserved
- Anthropic provider support
- OpenAI provider support
- All simulator logic and degradation models
- Agent Sim UI functionality
- A2A and LangGraph implementations for manual simulators

## Deployment

This directory was copied to `/home/john_harney/github/agentsim_ui` for standalone use.
