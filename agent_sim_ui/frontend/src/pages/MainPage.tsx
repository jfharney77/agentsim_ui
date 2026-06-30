import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Simulator } from "../types/api";
import { SimulatorCard } from "../components/SimulatorCard";
import { ArrowRight } from "lucide-react";

const CONCURRENCY_OPTIONS = [1, 2, 5, 10] as const;

export function MainPage() {
  const navigate = useNavigate();
  const [simulators, setSimulators] = useState<Simulator[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [concurrency, setConcurrency] = useState<number | null>(null);
  const [taskPrompt, setTaskPrompt] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listSimulators()
      .then(setSimulators)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const selected = simulators.find((s) => s.id === selectedId);
  const canLaunch = selectedId !== null && concurrency !== null && !launching;

  const handleLaunch = async () => {
    if (!selectedId || concurrency === null) return;
    setLaunching(true);
    setError(null);
    try {
      const response = await api.launch({
        simulator_id: selectedId,
        concurrency,
        task_prompt: taskPrompt || undefined,
      });
      navigate(`/run/${response.run_group_id}`);
    } catch (err: any) {
      setError(err.message || "Launch failed");
      setLaunching(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading simulators...</div>
      </div>
    );
  }

  if (error && simulators.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-red-600">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative overflow-hidden bg-slate-950 text-white">
      <div className="absolute inset-0 opacity-30 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.2),_transparent_55%),radial-gradient(circle_at_30%_30%,_rgba(59,130,246,0.2),_transparent_40%),radial-gradient(circle_at_bottom,_rgba(168,85,247,0.2),_transparent_60%)]" />
      <div className="relative max-w-6xl mx-auto px-6 py-12">
        <header className="mb-10">
          <p className="uppercase tracking-[0.3em] text-xs text-cyan-200/70 mb-3">
            Agent Simulation Launcher
          </p>
          <h1 className="text-4xl md:text-5xl font-semibold text-white mb-3">
            Choose a simulator. Launch a squad.
          </h1>
          <p className="text-slate-200 max-w-2xl">
            Discover the available simulators, review each agent roster, and spin up parallel runs in seconds.
          </p>
        </header>

        {simulators.length === 0 ? (
          <div className="bg-white/10 border border-white/20 rounded-2xl p-8 text-slate-200">
            No simulators were returned by the API.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-10">
            {simulators.map((sim) => (
              <SimulatorCard
                key={sim.id}
                simulator={sim}
                selected={selectedId === sim.id}
                onSelect={() => setSelectedId(sim.id)}
              />
            ))}
          </div>
        )}

        {selected && (
          <div className="bg-white/10 backdrop-blur border border-white/20 rounded-2xl p-6 shadow-xl">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
              <div>
                <h2 className="text-2xl font-semibold">{selected.name}</h2>
                <p className="text-slate-200 text-sm">
                  {selected.topology} topology · {selected.agents.length} agents
                </p>
              </div>
              <a
                href="/parallel"
                className="text-sm text-cyan-200 hover:text-white transition"
              >
                Need more than 10? Go to Parallel Sim →
              </a>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-200 mb-3">
                  Concurrency
                </label>
                <div className="flex flex-wrap gap-2">
                  {CONCURRENCY_OPTIONS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setConcurrency(c)}
                      className={`px-4 py-2 rounded-full border text-sm transition-colors ${
                        concurrency === c
                          ? "border-cyan-300 bg-cyan-300/20 text-white"
                          : "border-white/30 text-slate-200 hover:border-white/60"
                      }`}
                    >
                      {c}x
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  Select 1, 2, 5, or 10 parallel instances.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-3">
                  Task Prompt (optional)
                </label>
                <input
                  type="text"
                  value={taskPrompt}
                  onChange={(e) => setTaskPrompt(e.target.value)}
                  placeholder="Leave empty for default task"
                  className="w-full px-3 py-2 border border-white/30 rounded-lg bg-white/10 text-white placeholder:text-slate-400"
                />
              </div>
            </div>

            <div className="mt-6 flex items-center gap-4">
              <button
                type="button"
                onClick={handleLaunch}
                disabled={!canLaunch}
                className={`flex items-center gap-2 px-6 py-3 rounded-full font-medium transition-all ${
                  canLaunch
                    ? "bg-cyan-400 text-slate-900 hover:bg-cyan-300"
                    : "bg-white/20 text-slate-400 cursor-not-allowed"
                }`}
              >
                {launching ? "Launching..." : "Launch"}
                {!launching && <ArrowRight className="w-4 h-4" />}
              </button>

              {error && (
                <div className="text-sm text-red-300">{error}</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
