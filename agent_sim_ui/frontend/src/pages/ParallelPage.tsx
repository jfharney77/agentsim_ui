import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, X } from "lucide-react";
import { api } from "../lib/api";
import type { InstanceDescriptor, StateChangeEvent, Simulator } from "../types/api";
import { CompactInstanceCell } from "../components/CompactInstanceCell";
import { AggregateStats } from "../components/AggregateStats";
import { InstancePane } from "../components/InstancePane";

const CONCURRENCY_OPTIONS = [1, 2, 5, 10, 100, 1000] as const;

export function ParallelPage() {
  const navigate = useNavigate();
  const [simulators, setSimulators] = useState<Simulator[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [concurrency, setConcurrency] = useState<number>(10);
  const [taskPrompt, setTaskPrompt] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [runGroupId, setRunGroupId] = useState<string | null>(null);
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
    if (!runGroupId) return;
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
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading simulators...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 flex items-center gap-4">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              Parallel Sim
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Launch 1–1000 instances at scale
            </p>
          </div>
        </header>

        {!runGroupId ? (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Simulator
                </label>
                <select
                  value={selectedId || ""}
                  onChange={(e) => setSelectedId(e.target.value || null)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Concurrency
                </label>
                <select
                  value={concurrency}
                  onChange={(e) => setConcurrency(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Task Prompt (optional)
              </label>
              <input
                type="text"
                value={taskPrompt}
                onChange={(e) => setTaskPrompt(e.target.value)}
                placeholder="Leave empty for default task"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            <button
              type="button"
              onClick={handleLaunch}
              disabled={!canLaunch}
              className={`px-6 py-2 rounded-md font-medium transition-colors ${
                canLaunch
                  ? "bg-blue-600 hover:bg-blue-700 text-white"
                  : "bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed"
              }`}
            >
              {launching ? "Launching..." : "Launch"}
            </button>

            {showConfirm && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-xl max-w-md">
                  <h3 className="text-lg font-semibold mb-2">Confirm Large Launch</h3>
                  <p className="text-gray-600 dark:text-gray-400 mb-4">
                    You are about to launch {concurrency} instances. This may consume significant resources.
                  </p>
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => setShowConfirm(false)}
                      className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleLaunch}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition"
                    >
                      Confirm
                    </button>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="mt-4 p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-md text-red-700 dark:text-red-300 text-sm">
                {error}
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-semibold">
                  Run: {runGroupId.slice(0, 8)}
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {instances.length} instance{instances.length !== 1 ? "s" : ""}
                  {usePolling && " (polling mode)"}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setRunGroupId(null);
                    setInstances([]);
                    setDrillInInstance(null);
                  }}
                  className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md font-medium transition"
                >
                  New Run
                </button>
                <button
                  type="button"
                  onClick={handleCancel}
                  disabled={cancelling}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md font-medium transition disabled:opacity-50"
                >
                  {cancelling ? "Cancelling..." : "Cancel"}
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <AggregateStats instances={instances} />

            {drillInInstance ? (
              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => setDrillInInstance(null)}
                  className="mb-4 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                >
                  ← Back to grid
                </button>
                <InstancePane instance={drillInInstance} />
              </div>
            ) : (
              <div className="mt-6">
                <h3 className="font-semibold mb-3">Instances ({instances.length})</h3>
                <div className="grid grid-cols-10 sm:grid-cols-15 md:grid-cols-20 lg:grid-cols-25 gap-1">
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
  );
}
