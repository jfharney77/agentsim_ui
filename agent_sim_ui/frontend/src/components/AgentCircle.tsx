import { useState } from "react";
import { Eye } from "lucide-react";
import type { AgentRuntimeState } from "../types/api";
import { AGENT_STATE_COLORS, AGENT_STATE_LABELS } from "../lib/constants";

// Label sits ON the state-colored fill, so it must contrast with it:
// white on the saturated fills, muted slate on the light idle fill.
const LABEL_COLORS: Record<AgentRuntimeState["state"], string> = {
  errored: "#ffffff",
  completed: "#ffffff",
  running: "#ffffff",
  not_started: "#62707E",
};

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
        className="w-16 h-16 rounded-full flex items-center justify-center text-xs font-medium cursor-pointer transition-all duration-150 hover:scale-110"
        style={{
          backgroundColor: color,
          border: agent.state === "not_started" ? "1px solid #d7e2ee" : undefined,
          boxShadow:
            agent.state === "errored"
              ? `0 0 0 2px ${color}55, 0 2px 6px rgba(16, 24, 40, 0.12), 0 0 12px 2px rgba(226, 61, 61, 0.35)`
              : agent.state === "not_started"
                ? "0 0 0 2px #E3E9F155, 0 1px 3px rgba(16,24,40,.08)"
                : `0 0 0 2px ${color}55, 0 2px 6px rgba(16, 24, 40, 0.12)`,
          animation:
            agent.state === "running"
              ? "as-cell-pulse 1.3s ease-in-out infinite"
              : undefined,
        }}
        onClick={onClick}
      >
        <span
          className="line-clamp-2 text-[10px] leading-[1.15] text-center px-1.5 break-words"
          style={{ color: LABEL_COLORS[agent.state] }}
          title={`${agent.agent_name} — ${AGENT_STATE_LABELS[agent.state]}`}
        >
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
          className="absolute -top-2 -right-2 w-6 h-6 bg-dell hover:bg-dell-deep text-white rounded-full flex items-center justify-center shadow-md"
          title="View Context"
        >
          <Eye className="w-3 h-3" />
        </button>
      )}

      {hovered && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 bg-[#10233C] border border-white/10 text-xs rounded-[10px] p-3 shadow-[0_12px_32px_rgba(6,16,30,.45)] z-10 pointer-events-none">
          <div className="font-semibold mb-2 text-[#E9EFF6]">{agent.agent_name}</div>
          <div className="space-y-1 text-[#8AA0B8]">
            <div>State: <span className="font-medium text-[#c6d5e5]">{AGENT_STATE_LABELS[agent.state]}</span></div>
            <div>Role: <span className="font-medium text-[#c6d5e5]">{agent.agent_name}</span></div>
            {agent.started_at && (
              <div>Started: <span className="font-medium text-[#c6d5e5]">{formatTime(agent.started_at)}</span></div>
            )}
            {elapsed !== null && agent.state === "running" && (
              <div>Elapsed: <span className="font-medium text-[#c6d5e5]">{elapsed}s</span></div>
            )}
            {agent.ended_at && (
              <div>Ended: <span className="font-medium text-[#c6d5e5]">{formatTime(agent.ended_at)}</span></div>
            )}
            {agent.failure_modes.length > 0 && (
              <div className="mt-2 pt-2 border-t border-white/10">
                <div className="text-[#f26060] font-medium">Failure Modes:</div>
                {agent.failure_modes.map((fm, i) => (
                  <div key={i} className="text-[#f26060]">• {fm}</div>
                ))}
              </div>
            )}
          </div>
          <div className="absolute -bottom-[5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 rotate-45 bg-[#10233C] border-r border-b border-white/10" />
        </div>
      )}
    </div>
  );
}
