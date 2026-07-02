# Handoff: AgentSim Console — mesh monitor, parallel runs & context workspace

## Overview
A front-end for **AgentSim**, a simulator of an agentic mesh. It lets a user launch multi-agent
simulators (Swarm, Orchestrator, ChatDev, MetaGPT, HyperAgent), watch a single run's agents pass
messages across a live mesh, run hundreds/thousands of instances in parallel and spot failures at a
glance, and inspect each agent's LLM context window side-by-side. Visual language borrows Dell
Support styling (white utility bar + rounded search, dark hero with an "ask" box and gradient pills,
light content band with a blue icon rail) while keeping AgentSim's own identity and a dark
"mission-control" theme for the running views.

## About the Design Files
The files in this bundle are **design references built in HTML** (a single streaming
`Mesh Monitor.dc.html` "Design Component" + its `support.js` runtime). They are a **prototype of the
intended look and behavior — not production code to copy verbatim.**

Your task is to **recreate these designs in the existing `agentsim_ui` codebase** using its
established stack and patterns:
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS + `react-router-dom` + `lucide-react`
  (see `agent_sim_ui/frontend/`).
- **Backend:** FastAPI (see `agent_sim_ui/backend/app/`), with the pydantic contract already defined
  in `backend/app/models.py` and mirrored in `frontend/src/types/api.ts`.
- **Context viewer:** the separate `context_window` repo (branch `multi-viewer-workspace`) —
  its `Workspace.jsx` / `Viewer.jsx` / `ContextBar.jsx` already implement the multi-viewer, so the
  Context screen here is a styling+integration target, not a from-scratch build.

Rebuild with Tailwind classes + the existing components; do **not** ship the `.dc.html`/`support.js`
runtime. Where the prototype hardcodes a simulated run, wire the real API instead (details below).

## Fidelity
**High-fidelity.** Colors, typography, spacing, radii, and interactions are final. Recreate the UI
pixel-closely with Tailwind, then swap the mock simulation for live data. Exact tokens are in
**Design Tokens** below.

## How to view the prototype
Open `Mesh Monitor.dc.html` in a browser (it loads `support.js` beside it). It opens on the Landing
page; the top tabs (Setup · Live Run · Parallel · Context) switch screens. It's fully interactive:
Setup → pick instances → Launch routes to Live Run (1–10) or Parallel (100–1000); Cancel run opens a
confirm modal; the Tweaks panel recolors the live grid/mesh.

---

## Screens / Views
The app is a single component with an internal `view` state: `landing | launch | live | parallel |
context` (+ a `cancelOpen` modal flag). A shared dark top nav is present on every view.

### Shared top chrome
1. **White utility bar** (Dell pattern) — height ~48px, `background #fff`, `border-bottom 1px #e6ebf1`,
   padding `11px 26px`. Left: 26px ring badge (2px `#0076CE` border, 8px blue dot) + wordmark
   `AgentSim` (800/16px `#0076CE`) + ` Console` (500, `#5b6b7b`). Center: rounded search field
   (`border 1px #cdd6e0`, radius 6px) placeholder "Search runs, instances, or agents" with a
   magnifier button (`#f3f6fa` fill, blue stroke icon). Right: `US/EN ▾` (globe), `Docs`, `Sign in ▾`
   (person) — all 500/13px `#3d4a57`, 20px gap.
2. **Dark app nav** — padding `14px 26px`, `background linear-gradient(180deg,#0C1D31,#0A1727)`,
   `border-bottom 1px rgba(255,255,255,.08)`. Left: AGENTSIM badge (34px ring, 800/15px, letter-spacing
   .16em) — click = go to Landing. Center: pill tab group (`background rgba(255,255,255,.05)`, radius
   11px, 4px pad) with tabs **Setup · Live Run · Parallel · Context**; active tab = `#0076CE` fill,
   white text; inactive = `#8AA0B8`. Right (only on running views): `● LIVE` (green `#18A673` dot,
   blinking) + elapsed mm:ss (IBM Plex Mono), **Cancel run** (red-outline button → opens modal), and
   always **＋ New run** (blue-outline → Setup).

### 1. Landing (`view = 'landing'`) — calm front door
- **Dark hero**, centered, max-width 1060, padding ~58px 26px:
  - Eyebrow: "AGENTIC MESH SIMULATION", 600/12px IBM Plex Mono, letter-spacing .28em, `#5f7da0`.
  - Headline: "Watch agents think, at any scale.", 800/44px Hanken, `#E9EFF6`.
  - Subtitle: 400/16px `#8AA0B8`, max-width 640.
  - **Ask box** (white, radius 18px, pad 18px 20px, shadow `0 14px 44px rgba(0,0,0,.38)`, max-width 780):
    sparkle `✦` (`#7b5cf0`) + text input placeholder "Describe a run to launch — e.g. "Swarm, 100
    instances, analyze Acme Corp market position"" (bound to the shared `task`). Footer row: `0/200`
    counter (`#9aa7b4` mono) left; mic icon (outline SVG) + circular **gradient send** button (38px,
    `linear-gradient(135deg,#5b8def,#a86ad6,#e59ac0)`, white `→`) right.
  - **Gradient-border pills** (4), centered, radius 999px, transparent border over
    `linear-gradient(95deg,#2E93E6,#a24fd0)` (padding-box/border-box trick), white 600/13px:
    **New Swarm run** (→ Setup) · **Watch live mesh** (→ Live) · **Run at scale** (→ Parallel) ·
    **Inspect context** (→ Context).
  - Note: "Runs consume tokens. Provider settings" (link `#7fb8e8`).
- **Light content band** (`background #f4f6f9`, radius 18px, pad 26–28px):
  - Header "Jump back in" (800/20px `#12212F`) + right meta "5 simulators · 1 run active · anthropic"
    (`#0076CE` mono).
  - Grid `1fr 300px`:
    - Left: three **white nav cards** (radius 12px, border `#e2e8f0`, hover border `#0076CE`) each with a
      glyph (`◈ ▦ ▤` in `#0076CE`), title (700/15px `#12212F`), one-line desc (`#62707E`), "Open →"
      (`#0076CE` mono). Below: **Recent runs** white card — rows of `id` (blue mono) · `sim · N×` ·
      relative time · status pill.
    - Right: **blue icon rail** (Dell "Identify Or Search" pattern) — 5 full-width outline buttons,
      each an outline blue SVG icon + label (`#0076CE`, 600/13px), border `#d7e2ee`, radius 8px, hover
      border `#0076CE`. First item highlighted (`background #EAF3FB`, border `#cfe4f5`). Labels:
      **Browse simulators** (→ Setup) · **Detect active runs** (→ Live) · **Recently viewed** (→ Parallel)
      · **Context workspace** (→ Context) · **Docs & API**.

### 2. Setup (`view = 'launch'`) — Dell light "configure a run"
- Light band (`#f4f6f9`), centered white card 780px (border `#e2e8f0`, radius 16px, pad 34px 36px).
- Title "Configure a run" (800/27px `#12212F`), subtitle (`#62707E`).
- **Simulator** picker: 3-col grid of cards from `simOptions`. Each: name (700/15px), `topology · N
  agents` (mono `#62707E`), and full **agent roster** (`#8593A1`). Selected card = `background #EAF3FB`,
  `border 1.5px #0076CE`, subtle blue shadow; unselected = white, border `#e2e8f0`.
  Rosters: Swarm = Coordinator · Researcher · Analyst · Writer · Critic; Orchestrator = Hub · Planner ·
  Worker A · Worker B · Reducer; ChatDev = CEO · CTO · Programmer · Reviewer · Tester · Designer · CPO;
  MetaGPT = Product Manager · Architect · Project Manager · Engineer · QA; HyperAgent = Planner ·
  Navigator · Editor · Executor.
- **Agent scope** (NEW): choose whether to simulate the *entire mesh* or *isolate a workflow* by running
  only selected agents. A segmented **All agents / Select agents** toggle (`#EEF2F7`/`#DCE3EB`, active
  `#0076CE`) with a live summary on the right (`All 5 agents` or `3 of 5 agents`, `#0076CE`). In *Select*
  mode, the chosen simulator's roster renders as **toggle chips** (radius 999px; on = `#EAF3FB` /
  `1.5px #0076CE` / `#0076CE` text with a filled `#0076CE` dot; off = white / `#d7e2ee` / `#62707E` with a
  `#cbd6e4` dot) — click each to include/exclude. Helper text: "Simulate the whole mesh, or isolate one
  workflow by running only the agents you select. Out-of-scope agents show as OUT in the live mesh."
  The scope selection is stored as agent indices into the selected simulator's roster (see State) and
  flows into the Launch label and the Live mesh (out-of-scope nodes render dashed + `OUT`).
- **Concurrency** segmented control (`background #EEF2F7`, border `#DCE3EB`, radius 11px): 1 · 2 · 5 · 10
  · 100 · 1000; active = `#0076CE` fill/white, inactive = `#62707E`. Below it a live routing hint:
  "Selected **N instances** → opens **{Live Run · watch the mesh | Parallel · grid at scale}**".
- **Task prompt** (optional) white input (border `#cdd6e0`).
- **Launch** button (full width, `#0076CE`, white 700/15px): "▸ Launch N × {Simulator} · {scope summary}"
  (e.g. "▸ Launch 10 × Swarm · 3 of 5 agents"). On click → `view = N<=10 ? 'live' : 'parallel'`.

### 3. Live Run (`view = 'live'`) — dark, one run
- Run strip: "Live Run · {sim} · mesh · run {id} · anthropic".
- Grid `296px 1fr`:
  - Left: **Instances (1)** — one selected instance card (blue border) with 5 state chips + a plain-English
    status line; **Run info** panel (topology / elapsed / model rows).
  - Right: **live mesh** panel (`#0D1E33`) — an SVG graph of up to 5 nodes labeled with the selected
    simulator's roster names (Coordinator center; Researcher, Analyst, Writer, Critic around) and 8
    edges (4 spokes + 4 ring). Edges are dashed; "hot" edges (both endpoints in scope, one running)
    animate a flowing dash (`#3B9BEA`) and thicken; cold edges `#33475F`. Nodes are 28px circles filled
    by agent state (idle `#1C3454`, running `#F2A81E`, done `#18A673`, err `#E23D3D`), stroke = card bg,
    with the state word inside and the agent name below; running nodes emit an expanding "ping" ring.
    **Agent scope:** agents excluded on Setup render as a dashed, muted circle labeled **OUT** (fill
    `#122237`, dashed stroke `#2A3E58`, text `#4E637E`) and their edges drop to opacity ~.16 with no flow;
    they are not counted as active/done. Subtitle reads "Simulating {scope summary} · out-of-scope agents
    shown as OUT". The Run-info panel shows a `scope N / M agents` row, and the "Agents done" KPI
    denominator uses the scoped count. Below: KPI tiles (Agents done 2/{scope}, Active, Messages, Elapsed).
  - **Agent timeline** (Gantt): 5 rows, colored bars positioned by start/duration; the running agent's
    bar pulses. **Inspect agent context →** CTA (→ Context).

### 4. Parallel (`view = 'parallel'`) — dark, at scale
- Run strip: "Parallel · {N} instances · {sim} · run {id}".
- Grid `1fr 540px`:
  - Left: **KPI row** — Active (`#F2A81E`), Completed (`#37c592`), Errored (`#E23D3D`), Throughput/min
    (with a mini sparkline). **Instance activity** heatmap: a 20×6 grid of 24px rounded cells (of 120
    shown "of {N}"); each cell colored by its instance's **dominant** agent state (errored > running >
    completed > idle); running cells pulse + glow; errored cells glow red. Legend: Running/Completed/
    Errored/Idle.
  - Right sidebar:
    - **Instance drill-in** (#037): status pill + 5 agent rows (name, mini progress track colored by
      state, state pill, duration) + "Inspect agent context →".
    - **Run results** widget (**this needs a backend stub — see below**): header + endpoint hint, a
      **No error** tally (green) and **Error** tally (red), then a scrollable per-instance list: `#id`
      with a green `✓ no error` pill or a red `✗ error` pill + reason (e.g. `analyst · tool_timeout`,
      `critic · schema_violation`).

### 5. Context workspace (`view = 'context'`) — dark multi-viewer
Recreate by styling/integrating the `context_window` repo's `Workspace`/`Viewer`.
- Toolbar: **＋ Add viewer** (blue), "N viewers open · run … · #037", layout switch **▦ Grid / ▥ Columns
  / ◳ Tabs** (Grid active), and a category **legend** (System `#8b5cf6` · Human `#3b82f6` · AI `#10b981`
  · Tool call `#f59e0b` · Tool result `#ef4444` · Free `#24344a`).
- 3 viewer panels (Researcher / Analyst / Writer), each: a 3px top accent stripe in that panel's color;
  header = colored dot + `Agent · #037` + ✕; sub = `claude-sonnet-4.5` + amber `⚠ approx` tokenizer
  badge; the **context window bar** = horizontal segments (one per message, width ∝ tokens, colored by
  category) then a large `#24344a` free segment; a `used / window tok` line + `NN% used`; a **message
  timeline** (role chip + preview + token count per row); and a per-panel extra (Researcher: a
  token-chip **Tokens/Text** drill-down; Analyst: a **Compaction preview** callout; Writer: a session
  note). Sample content is the SMR research pipeline from `context_window/sample_state.json`.

### Cancel modal (`cancelOpen`)
Absolute overlay over the app frame (`background rgba(6,16,30,.74)`), centered dialog (420–430px,
`#10233C`, border `rgba(255,255,255,.12)`, radius 14px): title "Cancel this run?", body "All running
instances will stop immediately. Completed results and logs are kept.", buttons **Keep running**
(`closeCancel`) and **Cancel run** (`#E23D3D` → `confirmCancel`: stop + return to Landing).

---

## Interactions & Behavior
- **Concurrency routing:** picking 1/2/5/10 then Launch opens **Live Run**; 100/1000 opens **Parallel**.
  The Setup routing hint updates live with the selection.
- **Agent scope:** toggling *All agents* / *Select agents* and clicking roster chips updates the scope
  summary, the Launch label, and (after launch) which mesh nodes are active vs. `OUT`. Switching
  simulators re-keys the roster; scope indices are clamped to the new roster length.
- **Navigation:** the four nav tabs and the landing cards/rail set `view`. The AGENTSIM/AgentSim brand
  returns to Landing.
- **Cancel:** Cancel run (nav, running views only) → confirm modal → confirm returns to Landing.
- **Animations:** cell pulse `ascellpulse` (opacity 1↔.5, 1.3s); mesh edge flow `asedgeflow`
  (stroke-dashoffset, .9s linear); node ping `asping` (scale 1→2.3 + fade, 1.6s); LIVE dot blink
  `asblink` (1.4s). Card/rail hovers transition border-color to `#0076CE` (~.15s).
- **Tweaks:** the four agent-state colors are adjustable and recolor the live grid + mesh instantly
  (in the real app, expose as theme constants / settings).

## State Management
Prototype state (map to React state / router as appropriate):
- `view: 'landing'|'launch'|'live'|'parallel'|'context'` — top-level route (use `react-router` in-app;
  Setup routing sets it based on `concurrency`).
- `concurrency: 1|2|5|10|100|1000` — selected instance count (server allowlist is the same set; see
  `ALLOWED_CONCURRENCY` in `backend/app/api.py`).
- `sim: string` — selected simulator id.
- `scopeMode: 'all' | 'select'` — whether to run the whole mesh or a chosen subset.
- `scopeSel: number[]` — agent indices (into the selected simulator's roster) that are in scope when
  `scopeMode === 'select'`. Helpers: `currentRoster()` (names for `sim`), `scopeIndices()` (all indices
  when mode is `all`, else the filtered `scopeSel`), `isInScope(i)`, `toggleAgent(i)`. In the real app,
  send this to the launcher so only the selected agents are instantiated/stepped (see below).
- `task: string` — shared prompt (ask box + Setup input).
- `cancelOpen: boolean` — modal.
- Live data (mocked here) — in production comes from the API: `POST /api/launch` → `run_group_id` +
  instances; `GET /api/runs/{id}` snapshot; **SSE** `GET /api/runs/{id}/events` streaming
  `StateChangeEvent`s to drive the grid/mesh/timeline; `POST /api/runs/{id}/cancel`;
  `GET /api/instances/{id}/log`; context via `GET /api/instances/{id}/agents/{agent_id}/context` (or the
  `context_window` backend `POST /api/load` + `GET /api/message/{i}` per viewer session).
  Keep the existing **min-state-visible** debounce (`VITE_MIN_STATE_VISIBLE_MS`, default 1500ms) from
  `RunView.tsx` so fast transitions stay legible.

## Backend stub to add (Run results widget)
The Parallel "Run results" widget needs an error/no-error verdict per completed instance. Add to
`backend/app/api.py` (data already lives on `AgentRuntimeState.failure_modes` / `InstanceStatus`):
```
GET /api/instances/{instance_id}/result
  → { "instance_id": str, "error": bool, "failure_modes": [str], "status": InstanceStatus }
GET /api/runs/{run_group_id}/result
  → { "no_error": int, "error": int,
      "instances": [ { "instance_id": str, "index": int, "error": bool, "failure_modes": [str] } ] }
```
`error = status == FAILED or len(failure_modes) > 0`. This is a thin read over the launcher/run-store
that already exist; no new persistence required.

## Backend change to add (Agent scope)
The Setup **Agent scope** control lets the user run the whole mesh or just selected agents, so the
launch request must carry the selection. Extend the launch contract in `backend/app/models.py` +
`backend/app/api.py` (and mirror in `frontend/src/types/api.ts`):
```
POST /api/launch  { ..., simulator, concurrency, task,
                    agent_scope?: string[] }   # roster agent ids/names to run; omit/empty = all
```
In the launcher, when `agent_scope` is non-empty, instantiate/step only those agents for each instance
and mark the rest as **excluded** (a state distinct from the four runtime states — not idle/failed — so
the UI can render them as `OUT` and exclude them from active/done tallies). If your simulator classes
assume a fixed roster, the minimal version is to keep all agents but flag out-of-scope ones as
`excluded` and skip stepping them. The frontend already sends indices into the simulator roster; map
them to agent ids server-side.

## Design Tokens
**Brand / Dell**
- Dell Blue (primary): `#0076CE` · deep/hover `#005BA1` · on-dark link `#3B9BEA`, `#7fb8e8`
- Light headings/text: `#12212F` · light muted `#62707E`, `#8593A1` · light navy `#003E7E`

**Dark theme**
- App bg `#0A1727` · panels `#10233C`, `#0D1E33`/`#0D1D31` · nav gradient `#0C1D31 → #0A1727`
- Borders `rgba(255,255,255,.08)` · text `#E9EFF6` · muted `#8AA0B8`, `#7E93AB` · faint `#6a7d92`,
  `#5f7da0`

**Light band / cards**
- Band `#f4f6f9` · card `#fff` · borders `#e2e8f0`, `#cdd6e0`, `#d7e2ee` · rail highlight `#EAF3FB` /
  `#cfe4f5` · segmented `#EEF2F7` / `#DCE3EB`
- Utility bar `#fff`, border `#e6ebf1`, utility text `#3d4a57`

**Agent-state colors (tweakable)**
- Running `#F2A81E` (pill text on dark uses `#F2A81E`; "brighter" done text `#37c592`)
- Completed `#18A673` · Errored `#E23D3D` · Idle (grid) `#17293F`, (mesh, dark) `#1C3454`, (light) `#E3E9F1`

**Context category colors** (from `context_window`)
- system `#8b5cf6` · human `#3b82f6` · ai `#10b981` · tool_call `#f59e0b` · tool_result `#ef4444` ·
  other `#6b7280` · free `#1f2937` (dark-viz `#24344a`)

**Gradients**
- Pill border `linear-gradient(95deg,#2E93E6,#a24fd0)` · send button `linear-gradient(135deg,#5b8def,
  #a86ad6,#e59ac0)` · sparkle `#7b5cf0`

**Typography**
- UI/headings: **Hanken Grotesk** (400/500/600/700/800). Data, ids, labels, counters: **IBM Plex Mono**
  (400/500/600). Both via Google Fonts. Scale: hero 44px/800; screen titles 20–27px/800; card titles
  15–16px/700; body 12–16px/400; labels 11–12px mono, uppercase, letter-spacing .1–.28em.

**Radii:** pills 999px · cards 12–18px · inputs/segmented 6–11px · heatmap cells 5px · nodes 28px r.
**Shadows:** frame `0 24px 60px rgba(6,16,30,.4)` · light card `0 2px 12px rgba(30,50,80,.06)` · ask box
`0 14px 44px rgba(0,0,0,.38)` · gradient send/selected `0 4px 14px rgba(0,118,206,.14–.18)`.
**Spacing:** section padding 22–58px; card padding 14–36px; grid gaps 12–22px.

## Assets
- **Fonts:** Google Fonts — Hanken Grotesk + IBM Plex Mono. (In-repo, install via your existing font
  pipeline or `@fontsource`.)
- **Icons:** all inline outline SVGs (search, globe, person, mic, grid, radar, eye, columns, doc). In the
  React app, use **`lucide-react`** (already a dependency) — e.g. `Search`, `Globe`, `User`, `Mic`,
  `LayoutGrid`, `ScanSearch`, `Eye`, `Columns`, `FileText`, `ArrowLeft`, `ArrowRight`, `X`.
- **No raster images.** Glyphs `◈ ▦ ▤ ✦ → ✓ ✗` are Unicode; swap for lucide icons in production.

## Mapping to the existing repo
- **Landing / Setup** — new screens. Today `frontend/src/pages/MainPage.tsx` is the launcher and
  `ParallelPage.tsx` has the 1–1000 concurrency select — fold their logic into the new Setup + routing.
- **Parallel** → `pages/ParallelPage.tsx` (+ `components/CompactInstanceCell.tsx`, `AggregateStats.tsx`);
  add the **Run results** widget (new component) fed by the stub endpoint.
- **Live Run** → `pages/RunView.tsx` (+ `InstancePane.tsx`, `AgentCircle.tsx`); add the **mesh graph**
  view as a new component (SVG or a lib like `reactflow`), toggled alongside the existing circle layout.
- **Context** → integrate `context_window` (branch `multi-viewer-workspace`): `Workspace.jsx`,
  `Viewer.jsx`, `ContextBar.jsx`, `MessageTimeline.jsx`, `RoleThemePicker.jsx` — restyle to this dark
  Dell shell.
- **Contract** — reuse `frontend/src/types/api.ts` and `backend/app/models.py` as-is (`AgentState`
  four-state model, `Simulator`, `InstanceDescriptor`, `StateChangeEvent`, etc.).

## Files in this bundle
- `Mesh Monitor.dc.html` — the full interactive design (all five screens + modal + tweaks). Open in a
  browser to explore; read the markup/logic for exact values.
- `support.js` — runtime for the `.dc.html` (needed only to view the prototype; **not** for production).
- `README.md` — this document.
