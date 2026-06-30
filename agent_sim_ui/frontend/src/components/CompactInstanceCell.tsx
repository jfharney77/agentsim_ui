import { InstanceStatus } from "../types/api";
import { AGENT_STATE_COLORS } from "../lib/constants";

interface CompactInstanceCellProps {
  index: number;
  status: InstanceStatus;
  agentStates: Record<string, string>;
  onClick: () => void;
}

const STATUS_COLORS: Record<InstanceStatus, string> = {
  pending: "#e5e7eb", // gray-200
  running: "#fef08a", // yellow-200
  completed: "#bbf7d0", // green-200
  failed: "#fecaca", // red-200
  cancelled: "#d1d5db", // gray-300
};

export function CompactInstanceCell({ index, status, agentStates, onClick }: CompactInstanceCellProps) {
  const dominantState = Object.values(agentStates).reduce((acc, state) => {
    if (state === "errored") return "errored";
    if (state === "running" && acc !== "errored") return "running";
    if (state === "completed" && acc !== "errored" && acc !== "running") return "completed";
    return acc;
  }, "not_started");

  const bgColor = dominantState !== "not_started" ? AGENT_STATE_COLORS[dominantState as keyof typeof AGENT_STATE_COLORS] : STATUS_COLORS[status];

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-12 h-12 rounded border border-gray-300 hover:border-blue-500 transition-colors relative"
      style={{ backgroundColor: bgColor }}
      title={`Instance #${index + 1} - ${status}`}
    >
      <span className="text-xs font-medium text-gray-700">{index + 1}</span>
    </button>
  );
}
