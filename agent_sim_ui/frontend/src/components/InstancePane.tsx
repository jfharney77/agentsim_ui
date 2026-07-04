import { useState } from "react";
import { FileText } from "lucide-react";
import type { InstanceDescriptor, RunLog } from "../types/api";
import { AgentCircle } from "./AgentCircle";
import { LogViewer } from "./LogViewer";
import { ContextViewer } from "./ContextViewer";
import { api } from "../lib/api";

interface InstancePaneProps {
  instance: InstanceDescriptor;
}

export function InstancePane({ instance }: InstancePaneProps) {
  const [log, setLog] = useState<RunLog | null>(null);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [contextAgent, setContextAgent] = useState<{ agentId: string; agentName: string } | null>(null);

  const handleLogClick = async () => {
    if (showLog) {
      setShowLog(false);
      return;
    }
    setLogLoading(true);
    setLogError(null);
    try {
      const data = await api.getInstanceLog(instance.instance_id);
      setLog(data);
      setShowLog(true);
    } catch (err: any) {
      setLogError(err.message || "Failed to load log");
    } finally {
      setLogLoading(false);
    }
  };

  // Plain colored status words — no highlight boxes (Dell clean design).
  const statusColors: Record<string, string> = {
    pending: "text-[#8593A1]",
    running: "text-state-running",
    completed: "text-state-completed",
    failed: "text-state-errored",
    cancelled: "text-[#8593A1]",
  };

  const shortId = instance.instance_id.slice(0, 8);

  const totalAgents = instance.agents.length;
  const completedAgents = instance.agents.filter((a) => a.state === "completed").length;
  const hasErrored = instance.agents.some((a) => a.state === "errored");
  const progressPct = totalAgents > 0 ? (completedAgents / totalAgents) * 100 : 0;

  return (
    <div className="bg-white rounded-xl p-6 shadow-light-card border border-[#e2e8f0] transition-all hover:shadow-[0_4px_14px_rgba(0,118,206,.12)] hover:border-[#cdd6e0]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-lg text-[#12212F]">
            Instance #{instance.index + 1}
          </h3>
          <p className="text-sm text-[#62707E]">
            ID: <span className="font-mono text-xs">{shortId}</span>
          </p>
        </div>
        <span
          className={`text-xs font-semibold ${
            statusColors[instance.status] || "text-[#8593A1]"
          }`}
        >
          {instance.status}
        </span>
      </div>

      <div className="h-1 rounded-full bg-[#EEF2F7] mb-4">
        <div
          className={`h-1 rounded-full transition-all duration-500 ${
            hasErrored ? "bg-[#E23D3D]" : "bg-[#18A673]"
          }`}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      <div className="flex flex-wrap gap-3 justify-center mb-4">
        {instance.agents.map((agent) => (
          <AgentCircle
            key={agent.agent_id}
            agent={agent}
            onViewContext={() => setContextAgent({ agentId: agent.agent_id, agentName: agent.agent_name })}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={handleLogClick}
        className="flex items-center gap-2 text-sm text-dell hover:text-dell-deep transition"
      >
        <FileText className="w-4 h-4" />
        View log
      </button>

      {showLog && (
        <LogViewer
          log={log}
          loading={logLoading}
          error={logError}
          onClose={() => setShowLog(false)}
        />
      )}

      {contextAgent && (
        <ContextViewer
          instanceId={instance.instance_id}
          agentId={contextAgent.agentId}
          agentName={contextAgent.agentName}
          onClose={() => setContextAgent(null)}
        />
      )}
    </div>
  );
}
