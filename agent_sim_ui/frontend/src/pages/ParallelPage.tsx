import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { InstanceDescriptor, StateChangeEvent, Simulator } from "../types/api";
import { CompactInstanceCell } from "../components/CompactInstanceCell";
import { AggregateStats } from "../components/AggregateStats";
import { InstancePane } from "../components/InstancePane";
import { AppShell } from "../components/AppShell";

const CONCURRENCY_OPTIONS = [1, 2, 5, 10, 100, 1000] as const;

export function ParallelPage() {
  // When launched from Setup, the run group arrives as a route param and we
  // skip the built-in picker, jumping straight to the live grid.
  const { runGroupId: routeRunGroupId } = useParams<{ runGroupId?: string }>();
  const [simulators, setSimulators] = useState<Simulator[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [concurrency, setConcurrency] = useState<number>(10);
  const [taskPrompt, setTaskPrompt] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [runGroupId, setRunGroupId] = useState<string | null>(routeRunGroupId ?? null);
  const [instances, setInstances] = useState<InstanceDescriptor[]>([]);
  const [cancelling, setCancelling] = useState(false);
  const [usePolling, setUsePolling] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [drillInInstance, setDrillInInstance] = useState<InstanceDescriptor | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    api.listSimulators()
      .then(setSimulators)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!runGroupId) return;

    const loadRun = async () => {
      try {
        const data = await api.getRun(runGroupId);
        setInstances(data.instances);
      } catch (err: any) {
        setError(err.message || "Failed to load run");
      }
    };

    loadRun();

    const cleanup = api.streamEvents(
      runGroupId,
      (event: StateChangeEvent) => {
        setInstances((prev) =>
          prev.map((inst) => {
            if (inst.instance_id !== event.instance_id) return inst;
            return {
              ...inst,
              agents: inst.agents.map((agent) => {
                if (agent.agent_id !== event.agent_id) return agent;
                return {
                  ...agent,
                  state: event.new_state,
                  started_at: agent.started_at || (event.new_state === "running" ? event.ts : null),
                  ended_at: event.new_state === "completed" || event.new_state === "errored" ? event.ts : agent.ended_at,
                  failure_modes: event.failure_modes,
                  last_event: event.ts,
                };
              }),
            };
          })
        );
      },
      (err) => {
        console.warn("SSE failed, falling back to polling:", err);
        setUsePolling(true);
      }
    );

    if (usePolling) {
      pollIntervalRef.current = setInterval(loadRun, 3000);
    }

    return () => {
      cleanup();
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [runGroupId, usePolling]);

  const canLaunch = selectedId !== null && !launching && !runGroupId;

  const handleLaunch = async () => {
    if (!selectedId) return;
    if (concurrency >= 100 && !showConfirm) {
      setShowConfirm(true);
      return;
    }
    setShowConfirm(false);
    setLaunching(true);
    setError(null);
    try {
      const response = await api.launch({
        simulator_id: selectedId,
        concurrency,
        task_prompt: taskPrompt || undefined,
      });
      setRunGroupId(response.run_group_id);
      setInstances(response.instances);
    } catch (err: any) {
      setError(err.message || "Launch failed");
      setLaunching(false);
    }
  };

  const handleCancel = async () => {
    if (!runGroupId || cancelling) return;
    setCancelling(true);
    try {
      await api.cancelRun(runGroupId);
      const data = await api.getRun(runGroupId);
      setInstances(data.instances);
    } catch (err: any) {
      setError(err.message || "Failed to cancel run");
    } finally {
      setCancelling(false);
    }
  };

  const handleDrillIn = (instance: InstanceDescriptor) => {
    setDrillInInstance(instance);
  };

  if (loading) {
    return (
      <AppShell activeTab="parallel">
        <div className="bg-band min-h-[calc(100vh-97px)] flex items-center justify-center">
          <div className="text-[#62707E]">Loading simulators…</div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      activeTab="parallel"
      running={!!runGroupId}
      onCancel={handleCancel}
    >
      <div className="bg-band min-h-[calc(100vh-97px)] p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-6 flex items-baseline gap-4">
          <h1 className="text-[24px] font-normal text-[#12212F]">Parallel</h1>
          <p className="text-sm text-[#62707E]">
            Launch 1–1000 instances at scale
          </p>
        </header>

        {!runGroupId ? (
          <div className="bg-white rounded-xl p-6 shadow-light-card border border-[#e2e8f0] hover:border-[#cdd6e0] transition-colors">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div>
                <label className="block text-[13px] font-bold text-[#12212F] mb-2">
                  Simulator
                </label>
                <select
                  value={selectedId || ""}
                  onChange={(e) => setSelectedId(e.target.value || null)}
                  className="w-full px-3 py-2 border border-[#cdd6e0] rounded-md bg-white text-[#12212F] outline-none focus:border-dell"
                >
                  <option value="">Select a simulator</option>
                  {simulators.map((sim) => (
                    <option key={sim.id} value={sim.id}>
                      {sim.name} ({sim.topology})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[13px] font-bold text-[#12212F] mb-2">
                  Concurrency
                </label>
                <select
                  value={concurrency}
                  onChange={(e) => setConcurrency(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-[#cdd6e0] rounded-md bg-white text-[#12212F] outline-none focus:border-dell"
                >
                  {CONCURRENCY_OPTIONS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-[13px] font-bold text-[#12212F] mb-2">
                Task prompt <span className="font-normal text-[#8593A1]">(optional)</span>
              </label>
              <input
                type="text"
                value={taskPrompt}
                onChange={(e) => setTaskPrompt(e.target.value)}
                placeholder="Leave empty for the default task"
                className="w-full px-3 py-2 border border-[#cdd6e0] rounded-md bg-white text-[#12212F] outline-none focus:border-dell"
              />
            </div>

            <button
              type="button"
              onClick={handleLaunch}
              disabled={!canLaunch}
              className={`px-6 py-2 rounded-md font-medium transition-all active:scale-[.99] ${
                canLaunch
                  ? "bg-dell hover:bg-dell-deep text-white"
                  : "bg-[#EEF2F7] text-[#8593A1] cursor-not-allowed"
              }`}
            >
              {launching ? "Launching…" : "Launch"}
            </button>

            {showConfirm && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                <div className="bg-white rounded-xl p-6 shadow-xl max-w-md border border-[#e2e8f0]">
                  <h3 className="text-lg font-semibold text-[#12212F] mb-2">
                    Launch {concurrency} instances?
                  </h3>
                  <p className="text-[#62707E] mb-4">
                    Each instance runs the full simulator and consumes provider
                    tokens. Confirm to launch, or go back and lower the count.
                  </p>
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => setShowConfirm(false)}
                      className="px-4 py-2 bg-white border border-dell text-dell rounded-md hover:bg-[#EAF3FB] transition"
                    >
                      Go back
                    </button>
                    <button
                      type="button"
                      onClick={handleLaunch}
                      className="px-4 py-2 bg-dell text-white rounded-md hover:bg-dell-deep transition"
                    >
                      Launch
                    </button>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="mt-4 p-3 bg-[#FDEDEF] border border-[#f3c2c9] rounded-md text-state-errored text-sm">
                {error}
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-medium text-[#12212F]">
                  Run {runGroupId.slice(0, 8)}
                </h2>
                <p className="text-sm text-[#62707E]">
                  {instances.length} instance{instances.length !== 1 ? "s" : ""}
                  {usePolling && " (polling mode)"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setRunGroupId(null);
                  setInstances([]);
                  setDrillInInstance(null);
                }}
                className="px-4 py-2 bg-white border border-dell text-dell hover:bg-[#EAF3FB] rounded-md font-medium transition-all active:scale-[.99]"
              >
                New run
              </button>
            </div>

            <AggregateStats instances={instances} />

            {drillInInstance ? (
              <div className="mt-6 page-fade">
                <button
                  type="button"
                  onClick={() => setDrillInInstance(null)}
                  className="mb-4 text-sm text-dell hover:underline"
                >
                  ← Back to grid
                </button>
                <InstancePane instance={drillInInstance} />
              </div>
            ) : (
              <div className="mt-6 bg-white border border-[#e2e8f0] rounded-xl p-5 shadow-light-card">
                <h3 className="font-semibold text-[#12212F] mb-3">
                  Instances ({instances.length})
                </h3>
                <div className="grid grid-cols-10 sm:grid-cols-15 md:grid-cols-20 lg:grid-cols-25 gap-1.5">
                  {instances.map((instance) => {
                    const agentStates = instance.agents.reduce((acc, agent) => {
                      acc[agent.agent_id] = agent.state;
                      return acc;
                    }, {} as Record<string, string>);
                    return (
                      <CompactInstanceCell
                        key={instance.instance_id}
                        index={instance.index}
                        status={instance.status}
                        agentStates={agentStates}
                        onClick={() => handleDrillIn(instance)}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      </div>
    </AppShell>
  );
}
