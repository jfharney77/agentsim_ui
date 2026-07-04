import { useState } from "react";
import { Eye } from "lucide-react";
import type { AgentRuntimeState } from "../types/api";
import { AGENT_STATE_COLORS, AGENT_STATE_LABELS } from "../lib/constants";

interface AgentCircleProps {
  agent: AgentRuntimeState;
  onClick?: () => void;
  onViewContext?: () => void;
}

export function AgentCircle({ agent, onClick, onViewContext }: AgentCircleProps) {
  const [hovered, setHovered] = useState(false);
  const color = AGENT_STATE_COLORS[agent.state];

  const formatTime = (iso: string | null) => {
    if (!iso) return null;
    const date = new Date(iso);
    return date.toLocaleTimeString();
  };

  const elapsed = agent.started_at
    ? Math.floor((Date.now() - new Date(agent.started_at).getTime()) / 1000)
    : null;

  return (
    <div
      className="relative group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center text-xs font-medium cursor-pointer transition-colors duration-300 hover:scale-105"
        style={{
          backgroundColor: color,
          boxShadow:
            agent.state === "errored"
              ? `0 0 0 2px ${color}55, 0 2px 6px rgba(16, 24, 40, 0.12), 0 0 12px 2px rgba(226, 61, 61, 0.35)`
              : `0 0 0 2px ${color}55, 0 2px 6px rgba(16, 24, 40, 0.12)`,
          animation:
            agent.state === "running"
              ? "as-cell-pulse 1.3s ease-in-out infinite"
              : undefined,
        }}
        onClick={onClick}
      >
        <span className="truncate px-1 text-center" title={agent.agent_name}>
          {agent.agent_name}
        </span>
      </div>

      {hovered && onViewContext && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onViewContext();
          }}
          className="absolute -top-2 -right-2 w-6 h-6 bg-blue-600 hover:bg-blue-700 text-white rounded-full flex items-center justify-center shadow-md"
          title="View Context"
        >
          <Eye className="w-3 h-3" />
        </button>
      )}

      {hovered && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 bg-gray-900 text-white text-xs rounded-lg p-3 shadow-xl z-10 pointer-events-none">
          <div className="font-semibold mb-2">{agent.agent_name}</div>
          <div className="space-y-1">
            <div>State: <span className="font-medium">{AGENT_STATE_LABELS[agent.state]}</span></div>
            <div>Role: <span className="font-medium">{agent.agent_name}</span></div>
            {agent.started_at && (
              <div>Started: <span className="font-medium">{formatTime(agent.started_at)}</span></div>
            )}
            {elapsed !== null && agent.state === "running" && (
              <div>Elapsed: <span className="font-medium">{elapsed}s</span></div>
            )}
            {agent.ended_at && (
              <div>Ended: <span className="font-medium">{formatTime(agent.ended_at)}</span></div>
            )}
            {agent.failure_modes.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-700">
                <div className="text-red-400 font-medium">Failure Modes:</div>
                {agent.failure_modes.map((fm, i) => (
                  <div key={i} className="text-red-300">• {fm}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
