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
  const toParallel = routesToParallel(concurrency);

  const handleLaunch = async () => {
    if (!selectedId || launching) return;
    setLaunching(true);
    setError(null);
    try {
      const response = await api.launch({
        simulator_id: selectedId,
        concurrency,
        task_prompt: taskPrompt || undefined,
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
          <div className="text-center mb-2 text-[27px] font-extrabold text-[#12212F]">
            Configure a run
          </div>
          <div className="text-center mb-8 text-[14px] text-[#62707E]">
            Choose a simulator and how many instances to spin up. 1–10 opens the
            live mesh · 100–1000 opens the parallel grid.
          </div>

          {/* Simulator picker */}
          <div className="text-[12px] font-mono font-semibold tracking-[.1em] uppercase text-[#62707E] mb-3">
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
                    <div className="text-[11px] font-mono text-[#62707E] mb-2.5">
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

          {/* Concurrency segmented control */}
          <div className="text-[12px] font-mono font-semibold tracking-[.1em] uppercase text-[#62707E] mb-3">
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
                  className={`flex-1 py-2 rounded-lg text-[13px] font-mono font-medium transition-colors ${
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
          <div className="text-[12px] font-mono font-semibold tracking-[.1em] uppercase text-[#62707E] mb-3">
            Task prompt{" "}
            <span className="normal-case tracking-normal text-[#8593A1]">
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
              : `Launch ${concurrency} × ${selected?.name ?? "Simulator"}`}
          </button>
        </div>
      </div>
    </AppShell>
  );
}
