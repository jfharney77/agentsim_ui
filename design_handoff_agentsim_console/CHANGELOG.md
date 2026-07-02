# Changelog — AgentSim Console design handoff

This file lists what changed in the design between exports, so you can implement the delta as a
punch-list rather than re-reading the whole spec. Newest first. See `README.md` for full details and
exact design tokens; open `Mesh Monitor.dc.html` in a browser as the visual reference.

---

## v3 — Agent scope (current)
Adds the ability to simulate the **entire mesh, a single agent, or any subset of agents** serving one
workflow.

**New — Setup screen "Agent scope" section** (between Simulator and Concurrency):
- Segmented **All agents / Select agents** toggle (`#EEF2F7`/`#DCE3EB`, active `#0076CE`) with a live
  right-aligned summary: `All 5 agents` or `3 of 5 agents` (`#0076CE`).
- In **Select agents** mode, the chosen simulator's roster renders as **toggle chips** (radius 999px;
  on = `#EAF3FB` / `1.5px #0076CE` / `#0076CE` text + filled `#0076CE` dot; off = white / `#d7e2ee` /
  `#62707E` + `#cbd6e4` dot). Click to include/exclude each agent.
- Helper text: "Simulate the whole mesh, or isolate one workflow by running only the agents you
  select. Out-of-scope agents show as OUT in the live mesh."

**Changed — Launch button label:** now `▸ Launch {N} × {Simulator} · {scope summary}`
(e.g. `▸ Launch 10 × Swarm · 3 of 5 agents`).

**Changed — Live Run mesh is now scope-aware:**
- Mesh nodes are labeled with the **selected simulator's roster names** (previously hardcoded to
  Swarm's roster).
- Out-of-scope agents render as a **dashed, muted circle labeled `OUT`** (fill `#122237`, dashed stroke
  `#2A3E58`, text `#4E637E`); their edges drop to opacity ~.16 with no flow animation; they are excluded
  from active/done tallies.
- Subtitle: "Simulating {scope summary} · out-of-scope agents shown as OUT".
- Run-info panel gains a `scope N / M agents` row; the "Agents done" KPI denominator uses the scoped
  count.

**New — state:** `scopeMode: 'all' | 'select'` and `scopeSel: number[]` (agent indices into the
selected simulator's roster). Helpers: `currentRoster()`, `scopeIndices()`, `isInScope(i)`,
`toggleAgent(i)`. Switching simulators re-keys the roster; scope indices clamp to the new length.

**New — backend work (documented in README → "Backend change to add (Agent scope)"):**
- Extend `POST /api/launch` with optional `agent_scope?: string[]` (roster agent ids to run; empty/omit
  = all). Mirror in `backend/app/models.py` and `frontend/src/types/api.ts`.
- In the launcher, run/step only the in-scope agents; flag the rest as a new **`excluded`** state
  (distinct from the four runtime states) so the UI can render them as `OUT` and drop them from tallies.

### Implementation punch-list (v3)
- [ ] Add `agent_scope` to the launch request model + endpoint; thread to the launcher.
- [ ] Introduce an `excluded` agent state (or an `in_scope: bool` flag on the agent runtime state).
- [ ] Setup: build the Agent scope segmented toggle + roster chips (React + Tailwind), bound to local
      state; summary + Launch label reflect it.
- [ ] Live mesh component: render out-of-scope nodes as dashed `OUT`, fade their edges, exclude from
      active/done counts; label nodes from the selected simulator's roster.
- [ ] Run-info panel: add the `scope N / M agents` row; KPI "Agents done" denominator = scoped count.

---

## v2 — Dell Support styling fusion
Reworked the visual language to borrow Dell Support's structure while keeping AgentSim's identity.

- **New — Landing page** as the default view (calm front door): dark hero, eyebrow + headline +
  subtitle, and navigation into the other screens. Clicking the brand returns here.
- **New — white utility bar** (Dell pattern) above the dark app nav: brand lockup + rounded **search
  field** with blue magnifier button + right-side `US/EN ▾`, `Docs`, `Sign in ▾`.
- **New — dark hero "ask" box:** white rounded box with sparkle mark, natural-language run prompt,
  `0/200` counter, mic glyph, and a **blue→purple→pink gradient circular send** button.
- **New — gradient-border quick-action pills:** New Swarm run · Watch live mesh · Run at scale ·
  Inspect context.
- **New — light content band** ("Jump back in") with white nav cards, a **Recent runs** list, and a
  Dell-style **blue icon rail** (Browse simulators · Detect active runs · Recently viewed · Context
  workspace · Docs & API).
- **Changed — Setup** restyled to Dell's light "configure a run" layout (white card on a light band,
  white simulator cards w/ light-blue selected state, light segmented concurrency control, white
  input, solid Dell-blue Launch).
- **Added earlier in v2:** agent rosters on Setup simulator cards; **Cancel run → confirm modal**; the
  four agent-state colors exposed as tweakable theme values.
- **Tokens:** Dell Blue `#0076CE` primary; light band `#f4f6f9`; utility bar `#fff` / border
  `#e6ebf1`; gradient pill border `linear-gradient(95deg,#2E93E6,#a24fd0)`; send button
  `linear-gradient(135deg,#5b8def,#a86ad6,#e59ac0)`.

---

## v1 — Initial export
First handoff: unified dark "mission-control" app with Setup, Live Run (circle/mesh), Parallel
heatmap (100–1000 instances), and the Context workspace (multi-viewer context windows). Concurrency
routing (1–10 → Live Run, 100–1000 → Parallel). Four-state agent color model (idle / running /
completed / errored). Included the **Run results** widget on Parallel (error/no-error per instance)
with the backend stub `GET /api/instances/{id}/result` and `GET /api/runs/{id}/result`.
