# Langfuse Integration (Manual Simulators)

This document describes how Langfuse tracing works for the manual `swarm` and `orchestrator` simulators.

## Scope

Applies to:
- `simulators/manual/swarm/*`
- `simulators/manual/orchestrator/*`
- `simulators/manual/langfuse_tracer.py`
- `scripts/manual/start_*.sh` and `scripts/manual/run_*.sh`

Langfuse package version in this repo: `langfuse==4.10.0`.

## Required Environment Variables

Set in `.env`:

```bash
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
# Optional (defaults to Langfuse cloud host if omitted)
LANGFUSE_HOST=https://cloud.langfuse.com
```

If keys are missing, tracing is a no-op and agents still run.

## Run Model (Two Terminals)

1. Terminal 1 (long-lived agent servers):
```bash
./scripts/manual/start_swarm.sh
# or
./scripts/manual/start_orchestrator.sh
```

2. Terminal 2 (per pipeline invocation):
```bash
./scripts/manual/run_swarm.sh "Acme Corp"
# or
./scripts/manual/run_orchestrator.sh "Acme Corp"
```

`run_*` scripts generate a new `LANGFUSE_SESSION_ID` each invocation. This keeps sessions unique per pipeline run even while Terminal 1 remains up.

## Trace Correlation Strategy

A2A payloads include a session marker prefix:
- Prefix: `__LF_SESSION_ID__:`
- Encode/decode helpers: `inject_session_id()` and `extract_session_id()`

Agent traces use the extracted run-level session ID so all agent turns for one pipeline invocation are grouped under the same Langfuse session.

## Langfuse 4.10.0 Implementation Notes

`simulators/manual/langfuse_tracer.py` uses the 4.10.0-compatible pattern:

- `get_client()` for client initialization
- `propagate_attributes(trace_id=..., session_id=...)` with a **fresh UUID trace_id per agent turn**
- `start_as_current_observation(as_type="span", ...)` for root observation
- `start_as_current_observation(as_type="generation", ...)` for model generation child
- `update_current_trace(name=..., session_id=..., tags=..., metadata=...)` to set trace-level fields

This explicit trace ID creation prevents stale context reuse across repeated runs from Terminal 2.

## Degrading Agent Coverage

Both standard and degrading agent paths are traced:

- Standard turns: `trace_standard_agent(...)`
- Degrading turns: `trace_degrading_agent(...)`

Degrading traces also write numeric scores:
- `degradation_level`
- `call_severity`
- `cumulative_severity`
- `active_failure_count`
- `is_terminal`

## Troubleshooting

### Symptom: traces appear as "Unnamed" (often on 2nd run)

Checks:
1. Verify `langfuse==4.10.0` is installed in the active venv.
2. Ensure servers were restarted after tracer changes.
3. Confirm no errors like unsupported observation types.
4. Confirm logs show trace submission debug lines from `langfuse_tracer.py`.

Notes:
- `Unknown observation type: trace, falling back to span` indicates code incompatible with 4.10.0 API usage.
- `No module named 'langfuse.client'` indicates imports from non-existent/legacy paths.

### Symptom: no traces at all

Checks:
1. `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set in `.env`.
2. `.env` is sourced by the start/run scripts.
3. Outbound access to `LANGFUSE_HOST` is allowed.

### Symptom: different agents are not grouped together

Checks:
1. `run_swarm.sh`/`run_orchestrator.sh` is used (they set `LANGFUSE_SESSION_ID`).
2. Agent logs show `extract_session_id` with a UUID session.

## Quick Verification

Run two consecutive invocations from Terminal 2 without restarting Terminal 1:

```bash
./scripts/manual/run_swarm.sh "Amazon"
./scripts/manual/run_swarm.sh "Meta"
```

Expected in Langfuse:
- Two distinct sessions (one per run)
- Each run has named traces for researcher/analyst/writer
- Input/output present at trace level and generation/span level
