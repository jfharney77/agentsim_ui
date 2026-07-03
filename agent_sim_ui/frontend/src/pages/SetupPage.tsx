import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Play } from "lucide-react";
import { api } from "../lib/api";
import type { Simulator } from "../types/api";
import { AppShell } from "../components/AppShell";

const CONCURRENCY_OPTIONS = [1, 2, 5, 10, 100, 1000] as const;

/** 1–10 opens the live mesh; 100–1000 opens the parallel grid. */
function routesToParallel(concurrency: number) {
  return concurrency >= 100;
}

export function SetupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const initialTask = (location.state as { task?: string } | null)?.task ?? "";

  const [simulators, setSimulators] = useState<Simulator[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [concurrency, setConcurrency] = useState<number>(1);
  const [taskPrompt, setTaskPrompt] = useState<string>(initialTask);
  const [scopeMode, setScopeMode] = useState<"all" | "workflow" | "select">("all");
  const [scopeSel, setScopeSel] = useState<number[]>([]);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listSimulators()
      .then((sims) => {
        setSimulators(sims);
        setSelectedId((cur) => cur ?? sims[0]?.id ?? null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const selected = simulators.find((s) => s.id === selectedId);
  const roster = selected?.agents ?? [];
  const workflows = selected?.workflows ?? [];
  const toParallel = routesToParallel(concurrency);

  // Switching simulators re-keys the roster; clamp scope indices to its
  // length and drop a workflow selection the new simulator doesn't have.
  useEffect(() => {
    setScopeSel((cur) => cur.filter((i) => i < roster.length));
    setWorkflowId((cur) =>
      cur && workflows.some((w) => w.id === cur) ? cur : null
    );
    setScopeMode((cur) => (cur === "workflow" && workflows.length === 0 ? "all" : cur));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, roster.length]);

  const workflow = workflows.find((w) => w.id === workflowId) ?? null;
  const workflowIndices = (wf: { agent_ids: string[] } | null) =>
    wf
      ? roster.reduce<number[]>(
          (acc, a, i) => (wf.agent_ids.includes(a.agent_id) ? [...acc, i] : acc),
          []
        )
      : [];

  // In-scope roster indices: everything for "all", the predefined subset for
  // "workflow", or the hand-picked (sorted) subset for "select".
  const scopeIndices =
    scopeMode === "all"
      ? roster.map((_, i) => i)
      : scopeMode === "workflow"
      ? workflowIndices(workflow)
      : [...scopeSel].filter((i) => i < roster.length).sort((a, b) => a - b);
  const scopeSummary =
    scopeMode === "all"
      ? `All ${roster.length} agents`
      : scopeMode === "workflow" && workflow
      ? `${workflow.name} · ${scopeIndices.length} of ${roster.length} agents`
      : `${scopeIndices.length} of ${roster.length} agents`;

  // Clicking a chip always drops into hand-picked mode; from workflow mode the
  // selection is seeded with the workflow's agents so the click refines it.
  const toggleAgent = (i: number) => {
    const base = scopeMode === "workflow" ? workflowIndices(workflow) : scopeSel;
    setScopeMode("select");
    setScopeSel(
      base.includes(i) ? base.filter((x) => x !== i) : [...base, i]
    );
  };

  const handleLaunch = async () => {
    if (!selectedId || launching) return;
    setLaunching(true);
    setError(null);
    try {
      // Map in-scope roster indices → agent ids; omit when running the whole mesh.
      const agentScope =
        scopeMode !== "all" && scopeIndices.length < roster.length
          ? scopeIndices.map((i) => roster[i].agent_id)
          : undefined;
      const response = await api.launch({
        simulator_id: selectedId,
        concurrency,
        task_prompt: taskPrompt || undefined,
        agent_scope: agentScope,
      });
      // Concurrency routing: 1–10 → Live Run, 100–1000 → Parallel grid.
      if (toParallel) {
        navigate(`/parallel/${response.run_group_id}`);
      } else {
        navigate(`/run/${response.run_group_id}`);
      }
    } catch (err: any) {
      setError(err.message || "Launch failed");
      setLaunching(false);
    }
  };

  return (
    <AppShell activeTab="setup">
      <div className="bg-band px-[26px] pt-11 pb-[52px] flex justify-center min-h-[calc(100vh-97px)]">
        <div className="w-full max-w-[780px] bg-white border border-[#e2e8f0] rounded-2xl px-9 py-[34px] shadow-light-card self-start">
          <div className="text-center mb-2 text-[30px] font-light text-[#12212F]">
            Configure a run
          </div>
          <div className="text-center mb-8 text-[14px] text-[#62707E]">
            Choose a simulator and how many instances to spin up. 1–10 opens the
            live mesh · 100–1000 opens the parallel grid.
          </div>

          {/* Simulator picker */}
          <div className="text-[13px] font-bold text-[#12212F] mb-3">
            Simulator
          </div>
          {loading ? (
            <div className="text-[#62707E] text-sm mb-[30px]">
              Loading simulators…
            </div>
          ) : simulators.length === 0 ? (
            <div className="text-[#62707E] text-sm mb-[30px]">
              No simulators available.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-[30px]">
              {simulators.map((sim) => {
                const active = sim.id === selectedId;
                return (
                  <button
                    key={sim.id}
                    type="button"
                    onClick={() => setSelectedId(sim.id)}
                    className={`text-left rounded-xl p-3.5 cursor-pointer transition-all ${
                      active
                        ? "bg-[#EAF3FB] border-[1.5px] border-dell shadow-[0_4px_14px_rgba(0,118,206,.16)]"
                        : "bg-white border-[1.5px] border-[#e2e8f0] hover:border-[#cdd6e0]"
                    }`}
                  >
                    <div className="text-[15px] font-bold text-[#12212F] mb-1">
                      {sim.name}
                    </div>
                    <div className="text-[11px] text-[#62707E] mb-2.5">
                      {sim.topology} · {sim.agents.length} agents
                    </div>
                    <div className="text-[10.5px] leading-[1.55] text-[#8593A1]">
                      {sim.agents.map((a) => a.agent_name).join(" · ")}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* Agent scope */}
          <div className="flex items-center justify-between mb-3">
            <div className="text-[13px] font-bold text-[#12212F]">
              Agent scope
            </div>
            <div className="text-[12px] text-dell font-medium">{scopeSummary}</div>
          </div>
          <div className="flex gap-1 bg-[#EEF2F7] border border-[#DCE3EB] rounded-[11px] p-[5px] mb-3 w-fit">
            {(["all", "workflow", "select"] as const).map((mode) => {
              if (mode === "workflow" && workflows.length === 0) return null;
              const active = scopeMode === mode;
              return (
                <button
                  key={mode}
                  type="button"
                  onClick={() => {
                    setScopeMode(mode);
                    // Entering workflow/select mode with no prior pick defaults
                    // to a sensible starting scope.
                    if (mode === "workflow" && !workflow && workflows[0]) {
                      setWorkflowId(workflows[0].id);
                    }
                    if (mode === "select" && scopeSel.length === 0) {
                      setScopeSel(roster.map((_, i) => i));
                    }
                  }}
                  className={`px-4 py-2 rounded-lg text-[12.5px] font-semibold transition-colors ${
                    active ? "bg-dell text-white" : "text-[#62707E] hover:text-[#12212F]"
                  }`}
                >
                  {mode === "all"
                    ? "All agents"
                    : mode === "workflow"
                    ? "Workflow"
                    : "Select agents"}
                </button>
              );
            })}
          </div>
          {scopeMode === "workflow" && workflows.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              {workflows.map((wf) => {
                const active = wf.id === workflowId;
                const count = workflowIndices(wf).length;
                return (
                  <button
                    key={wf.id}
                    type="button"
                    onClick={() => setWorkflowId(wf.id)}
                    className={`text-left rounded-xl p-3.5 cursor-pointer transition-all ${
                      active
                        ? "bg-[#EAF3FB] border-[1.5px] border-dell shadow-[0_4px_14px_rgba(0,118,206,.16)]"
                        : "bg-white border-[1.5px] border-[#e2e8f0] hover:border-[#cdd6e0]"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2 mb-1">
                      <span className="text-[14px] font-bold text-[#12212F]">
                        {wf.name}
                      </span>
                      <span className="text-[11px] text-dell">
                        {count} of {roster.length}
                      </span>
                    </div>
                    <div className="text-[11.5px] leading-[1.5] text-[#8593A1]">
                      {wf.description}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
          {/* Full mesh roster — every agent stays visible; chips show what is
              in scope. Clicking one refines into hand-picked (Select) mode. */}
          {scopeMode !== "all" && (
            <div className="flex flex-wrap gap-2 mb-3">
              {roster.map((agent, i) => {
                const on = scopeIndices.includes(i);
                return (
                  <button
                    key={agent.agent_id}
                    type="button"
                    onClick={() => toggleAgent(i)}
                    className={`flex items-center gap-[7px] rounded-full pl-[11px] pr-3.5 py-2 text-[12.5px] font-semibold transition-colors ${
                      on
                        ? "bg-[#EAF3FB] border-[1.5px] border-dell text-dell"
                        : "bg-white border border-[#d7e2ee] text-[#62707E] hover:border-[#cdd6e0]"
                    }`}
                  >
                    <span
                      className="inline-block w-[9px] h-[9px] rounded-[3px]"
                      style={{ background: on ? "#0076CE" : "#cbd6e4" }}
                    />
                    {agent.agent_name}
                    {!on && (
                      <span className="text-[9px] font-semibold text-[#8593A1]">OUT</span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
          <div className="text-[12.5px] leading-[1.5] text-[#8593A1] mb-[30px]">
            Simulate the whole mesh, run a predefined workflow, or isolate any
            subset of agents. Out-of-scope agents show as{" "}
            <span className="text-[#62707E] font-semibold">OUT</span> in the live
            mesh.
          </div>

          {/* Concurrency segmented control */}
          <div className="text-[13px] font-bold text-[#12212F] mb-3">
            Concurrency
          </div>
          <div className="flex gap-1 bg-[#EEF2F7] border border-[#DCE3EB] rounded-[11px] p-[5px] mb-[11px]">
            {CONCURRENCY_OPTIONS.map((n) => {
              const active = n === concurrency;
              return (
                <button
                  key={n}
                  type="button"
                  onClick={() => setConcurrency(n)}
                  className={`flex-1 py-2 rounded-lg text-[13px] font-medium transition-colors ${
                    active
                      ? "bg-dell text-white"
                      : "text-[#62707E] hover:text-[#12212F]"
                  }`}
                >
                  {n}
                </button>
              );
            })}
          </div>
          <div className="text-[13px] text-[#62707E] mb-[30px]">
            Selected{" "}
            <span className="text-dell font-semibold">
              {concurrency} instances
            </span>{" "}
            → opens{" "}
            <span className="text-[#12212F] font-semibold">
              {toParallel ? "Parallel · grid at scale" : "Live Run · watch the mesh"}
            </span>
          </div>

          {/* Task prompt */}
          <div className="text-[13px] font-bold text-[#12212F] mb-3">
            Task prompt{" "}
            <span className="font-normal text-[#8593A1]">
              (optional)
            </span>
          </div>
          <input
            type="text"
            value={taskPrompt}
            onChange={(e) => setTaskPrompt(e.target.value)}
            placeholder="Analyze Acme Corp market position"
            className="w-full box-border px-[15px] py-[13px] rounded-[10px] bg-white border border-[#cdd6e0] text-[#1B2733] text-[14px] outline-none focus:border-dell mb-7"
          />

          {error && (
            <div className="text-[13px] text-state-errored mb-4">{error}</div>
          )}

          {/* Launch */}
          <button
            type="button"
            onClick={handleLaunch}
            disabled={!selectedId || launching}
            className="flex items-center justify-center gap-2 w-full py-4 rounded-[11px] bg-dell hover:bg-dell-deep disabled:opacity-60 disabled:cursor-not-allowed text-white text-[15px] font-bold transition-colors"
          >
            <Play className="w-4 h-4 fill-white" />
            {launching
              ? "Launching…"
              : `Launch ${concurrency} × ${
                  selected?.name ?? "Simulator"
                } · ${scopeSummary}`}
          </button>
        </div>
      </div>
    </AppShell>
  );
}
