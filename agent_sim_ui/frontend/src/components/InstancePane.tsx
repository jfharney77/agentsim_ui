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

  const statusColors: Record<string, string> = {
    pending: "bg-gray-200 text-gray-700",
    running: "bg-yellow-200 text-yellow-800",
    completed: "bg-green-200 text-green-800",
    failed: "bg-red-200 text-red-800",
    cancelled: "bg-gray-300 text-gray-700",
  };

  const shortId = instance.instance_id.slice(0, 8);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-lg">Instance #{instance.index + 1}</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            ID: <span className="font-mono text-xs">{shortId}</span>
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            statusColors[instance.status] || "bg-gray-200 text-gray-700"
          }`}
        >
          {instance.status}
        </span>
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
        className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition"
      >
        <FileText className="w-4 h-4" />
        View Log
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
