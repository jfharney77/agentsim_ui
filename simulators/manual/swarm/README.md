# A2A Swarm — 3 peer agents, no orchestrator

A minimal but **real** [A2A](https://a2a-protocol.org) swarm you can run and poke at locally.
Three independent agents, each its own HTTP server with its own published Agent Card,
collaborating peer-to-peer with **no orchestrator**:

```
client → Researcher → Analyst → Writer → final briefing
         (9001)        (9002)     (9003)
```

Each agent does real work via the Anthropic API. The handoff order is the swarm's
own wiring, not a routing agent — that's what makes it a swarm rather than an
orchestrator-worker setup.

## What's actually A2A here (not simulated)

- Each agent serves a real card at `/.well-known/agent-card.json` over HTTP.
- The client **discovers** peers by fetching those cards, then **inspects** each
  card's `skills` to confirm the peer can do what's needed before sending work.
- Work is sent via real `message/send` JSON-RPC calls through the `a2a-sdk` client.
- An agent's LLM call is **opaque** to its peers — they see only the result message.

## Setup

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

Terminal 1 — start the three agents:

```bash
./scripts/manual/start_swarm.sh
```

Terminal 2 — run the swarm against a topic:

```bash
./scripts/manual/run_swarm.sh "Acme Corp" # Test company
```

Alternatively, you can run the swarm directly with Python:

```bash
python -m simulators.manual.swarm.swarm "Acme Corp" # Test company
```

You'll see a DISCOVERY phase (cards fetched + skills validated) followed by three
HANDOFF phases, ending in the Writer's final briefing.

## Files

| File | Role |
|------|------|
| `simulators/manual/swarm/brain.py` | Shared Anthropic wrapper — the "work" each agent does |
| `simulators/manual/swarm/server.py` | Factory: turns a role into a real A2A server (card + executor) |
| `simulators/manual/swarm/agentic_mesh/langgraph/researcher.py` / `analyst.py` / `writer.py` | The three roles (card + system prompt) — or use a2a/ variants |
| `simulators/manual/swarm/swarm.py` | Discovers peers and chains the peer-to-peer handoffs |
| `scripts/manual/start_swarm.sh` | Launches all three agents with a readiness wait |
| `scripts/manual/run_swarm.sh` | Runs the swarm against a given topic |

## Things to experiment with

- **Add a 4th peer** (e.g. a `fact_checker`) and route Analyst → Fact-checker → Writer.
- **Make it a real mesh**: let the Analyst call back to the Researcher if facts are
  thin — that's the O(n²) discovery growth from the theory made concrete.
- **Break discovery**: stop one agent and watch the skill-validation step fail. This
  is the unstandardized-registry problem in miniature — discovery is the load-bearing
  weakness of a swarm.
- **Add shared state**: right now state is just passed hand-to-hand. Add a shared
  store (a dict, then Redis) that all agents read/write — the "blackboard" pattern.

## Where a monitoring agent would hook in

This swarm has the exact blind spot discussed in the APIP/mesh work: there's **no
single trace** of the whole run, because no orchestrator sees everything. To monitor it:

- Wrap `think()` in `brain.py` with timing/token/outcome capture (your Cat 1 / Cat 2 split).
- Better: instrument each agent server with **OpenTelemetry** spans and tie them
  together by a shared `context_id` (A2A's correlation key) so you can reconstruct
  the cross-agent trace a swarm otherwise lacks.
- A watcher would consume those spans and apply contract-driven thresholds —
  exactly the layer no vendor ships out of the box.

## Version note (important)

Built and tested against **`a2a-sdk==0.3.7`** (the stable Pydantic API every current
tutorial uses). A2A reached v1.0 in March 2026 and the **`a2a-sdk` 1.x line is a
protobuf-based rewrite with a different, less-documented API** (types come from
`a2a_pb2`, not Pydantic). If you `pip install` an unpinned `a2a-sdk` you'll likely
get 1.x and this code will not import as-is. Keep the pin, or budget time to port.
The protocol moves fast — verify against the live SDK if something drifts.