import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { X, ArrowLeft } from "lucide-react";
import { api } from "../lib/api";
import type { InstanceDescriptor, StateChangeEvent } from "../types/api";
import { InstancePane } from "../components/InstancePane";
import { AGENT_STATE_COLORS, AGENT_STATE_LABELS } from "../lib/constants";

export function RunView() {
  const { runGroupId } = useParams<{ runGroupId: string }>();
  const navigate = useNavigate();
  const [instances, setInstances] = useState<InstanceDescriptor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [usePolling, setUsePolling] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastUpdateRef = useRef<Map<string, number>>(new Map());
  const timersRef = useRef<Map<string, number>>(new Map());
  const pendingRef = useRef<Map<string, StateChangeEvent>>(new Map());
  const MIN_STATE_VISIBLE_MS = parseInt(import.meta.env.VITE_MIN_STATE_VISIBLE_MS || "1500", 10);

  const applyEvent = (event: StateChangeEvent) => {
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
    const key = `${event.instance_id}:${event.agent_id}`;
    lastUpdateRef.current.set(key, Date.now());
  };

  const scheduleEvent = (event: StateChangeEvent) => {
    const key = `${event.instance_id}:${event.agent_id}`;
    const now = Date.now();
    const last = lastUpdateRef.current.get(key);
    const isTerminal = event.new_state === "completed" || event.new_state === "errored";
    if (isTerminal && last && now - last < MIN_STATE_VISIBLE_MS) {
        const delay = MIN_STATE_VISIBLE_MS - (now - last);
        const existing = timersRef.current.get(key);
        if (existing) {
          window.clearTimeout(existing);
        }
        pendingRef.current.set(key, event);
        const timer = window.setTimeout(() => {
          const pending = pendingRef.current.get(key);
          if (pending) {
            applyEvent(pending);
          }
          pendingRef.current.delete(key);
          timersRef.current.delete(key);
        }, delay);
        timersRef.current.set(key, timer);
        return;
    }
    applyEvent(event);
  };

  useEffect(() => {
    if (!runGroupId) return;

    const loadRun = async () => {
      try {
        const data = await api.getRun(runGroupId);
        setInstances(data.instances);
        setLoading(false);
      } catch (err: any) {
        setError(err.message || "Failed to load run");
        setLoading(false);
      }
    };

    loadRun();

    // Try SSE first
    const cleanup = api.streamEvents(
      runGroupId,
      (event: StateChangeEvent) => {
        scheduleEvent(event);
      },
      (err) => {
        console.warn("SSE failed, falling back to polling:", err);
        setUsePolling(true);
      }
    );

    // Fallback polling if SSE fails
    if (usePolling) {
      pollIntervalRef.current = setInterval(loadRun, 2000);
    }

    return () => {
      cleanup();
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      for (const timer of timersRef.current.values()) {
        window.clearTimeout(timer);
      }
      timersRef.current.clear();
      pendingRef.current.clear();
    };
  }, [runGroupId, usePolling]);

  const handleCancel = async () => {
    if (!runGroupId) return;
    setCancelling(true);
    try {
      await api.cancelRun(runGroupId);
      // Refresh after cancel
      const data = await api.getRun(runGroupId);
      setInstances(data.instances);
    } catch (err: any) {
      setError(err.message || "Failed to cancel run");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading run...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-red-600">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => navigate("/")}
              className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                Run: {runGroupId?.slice(0, 8)}
              </h1>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {instances.length} instance{instances.length !== 1 ? "s" : ""}
                {usePolling && " (polling mode)"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md font-medium transition disabled:opacity-50"
          >
            {cancelling ? "Cancelling..." : "Cancel Run"}
            <X className="w-4 h-4" />
          </button>
        </header>

        {/* Legend */}
        <div className="flex gap-4 mb-6 text-sm">
          {Object.entries(AGENT_STATE_COLORS).map(([state, color]) => (
            <div key={state} className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded-full border border-gray-300"
                style={{ backgroundColor: color }}
              />
              <span className="text-gray-700 dark:text-gray-300">
                {AGENT_STATE_LABELS[state as keyof typeof AGENT_STATE_LABELS]}
              </span>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {instances.map((instance) => (
            <InstancePane key={instance.instance_id} instance={instance} />
          ))}
        </div>
      </div>
    </div>
  );
}
