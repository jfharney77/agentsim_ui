# A2A Orchestrator Pattern - Hub and Spoke

This package runs the same three-role workflow (research -> analysis -> writing)
but with a central orchestrator hub instead of peer-to-peer handoffs.

Flow:

client -> hub -> researcher worker
client <- hub <- researcher worker
client -> hub -> analyst worker
client <- hub <- analyst worker
client -> hub -> writer worker
client <- hub <- writer worker

## Setup

Install dependencies once from the swarm package:

```bash
pip install -r simulators/manual/swarm/requirements.txt
```

Configure your API key and implementation by setting environment variables in `.env`:

```bash
# Choose implementation for each agent: a2a, langgraph, degrading-a2a, degrading-langgraph
RESEARCHER_IMPL=langgraph
ANALYST_IMPL=degrading-langgraph
WRITER_IMPL=langgraph
```

## Run

Terminal 1 - start workers:

```bash
./scripts/manual/start_orchestrator.sh
```

Terminal 2 - run the hub:

```bash
./scripts/manual/run_orchestrator.sh "Acme Corp" # Test company
```

Alternatively, you can run the hub directly with Python:

```bash
python -m simulators.manual.orchestrator.hub "Acme Corp" # Test company
```

## Files

- `simulators/manual/orchestrator/hub.py`: central coordinator that discovers workers and dispatches each stage
- `simulators/manual/orchestrator/server.py`: worker A2A server factory
- `simulators/manual/orchestrator/agentic_mesh/langgraph/researcher.py`: research worker # or a2a/researcher.py
- `simulators/manual/orchestrator/agentic_mesh/langgraph/analyst.py`: analysis worker # or a2a/analyst.py
- `simulators/manual/orchestrator/agentic_mesh/langgraph/writer.py`: writer worker # or a2a/writer.py
- `simulators/manual/orchestrator/brain.py`: shared Anthropic wrapper
- `scripts/manual/start_orchestrator.sh`: starts worker servers and waits for readiness
- `scripts/manual/run_orchestrator.sh`: runs the orchestrator against a given topic