import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { InstanceDescriptor, StateChangeEvent } from "../types/api";
import { InstancePane } from "../components/InstancePane";
import { LiveMesh } from "../components/LiveMesh";
import { AppShell } from "../components/AppShell";
import { AgentState } from "../types/api";
import { AGENT_STATE_COLORS, AGENT_STATE_LABELS } from "../lib/constants";

export function RunView() {
  const { runGroupId } = useParams<{ runGroupId: string }>();
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
    if (!runGroupId || cancelling) return;
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
      <AppShell activeTab="live">
        <div className="bg-band min-h-[calc(100vh-97px)] flex items-center justify-center">
          <div className="text-[#62707E]">Loading run…</div>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell activeTab="live">
        <div className="bg-band min-h-[calc(100vh-97px)] flex items-center justify-center">
          <div className="text-state-errored">Error: {error}</div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell activeTab="live" running onCancel={handleCancel}>
      <div className="bg-band min-h-[calc(100vh-97px)] p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-6 flex items-baseline gap-4">
          <h1 className="text-[24px] font-normal text-[#12212F]">
            Run {runGroupId?.slice(0, 8)}
          </h1>
          <p className="text-sm text-[#62707E]">
            {instances.length} instance{instances.length !== 1 ? "s" : ""}
            {usePolling && " (polling mode)"}
          </p>
        </header>

        {/* Legend */}
        <div className="flex gap-4 mb-6 text-sm">
          {Object.entries(AGENT_STATE_COLORS).map(([state, color]) => (
            <div key={state} className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded-full border border-[#D2D2D2]"
                style={{ backgroundColor: color }}
              />
              <span className="text-[#62707E]">
                {AGENT_STATE_LABELS[state as keyof typeof AGENT_STATE_LABELS]}
              </span>
            </div>
          ))}
        </div>

        {/* Live mesh for the first instance (scope-aware: out-of-scope agents show as OUT). */}
        {instances[0] && (() => {
          const inst = instances[0];
          const scoped = inst.agents.filter((a) => a.in_scope !== false);
          const total = inst.agents.length;
          const done = scoped.filter((a) => a.state === AgentState.COMPLETED).length;
          const active = scoped.filter((a) => a.state === AgentState.RUNNING).length;
          const scopeSummary =
            scoped.length === total
              ? `All ${total} agents`
              : `${scoped.length} of ${total} agents`;
          return (
            <div className="mb-6 rounded-2xl bg-[#0D1E33] border border-white/10 p-6">
              <div className="flex items-start justify-between mb-4 flex-wrap gap-4">
                <div>
                  <div className="text-[16px] font-bold text-[#E9EFF6]">
                    Instance #{inst.index + 1} · live mesh
                  </div>
                  <div className="text-[12px] text-[#8AA0B8] mt-1">
                    Simulating {scopeSummary} · out-of-scope agents shown as OUT
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="rounded-lg bg-white/[.04] px-4 py-2 text-center min-w-[92px]">
                    <div className="text-[11px] text-[#7E93AB]">
                      Agents done
                    </div>
                    <div className="text-[18px] font-bold text-[#37c592]">
                      {done}
                      <span className="text-[#7E93AB]">/{scoped.length}</span>
                    </div>
                  </div>
                  <div className="rounded-lg bg-white/[.04] px-4 py-2 text-center min-w-[92px]">
                    <div className="text-[11px] text-[#7E93AB]">
                      Active
                    </div>
                    <div className="text-[18px] font-bold text-[#F2A81E]">{active}</div>
                  </div>
                  <div className="rounded-lg bg-white/[.04] px-4 py-2 text-center min-w-[92px]">
                    <div className="text-[11px] text-[#7E93AB]">
                      Scope
                    </div>
                    <div className="text-[18px] font-bold text-[#E9EFF6]">
                      {scoped.length}
                      <span className="text-[#7E93AB]">/{total}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex justify-center">
                <LiveMesh instance={inst} />
              </div>
            </div>
          );
        })()}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {instances.map((instance) => (
            <InstancePane key={instance.instance_id} instance={instance} />
          ))}
        </div>
      </div>
      </div>
    </AppShell>
  );
}
