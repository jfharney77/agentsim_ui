import { InstanceStatus, AgentState } from "../types/api";
import { AGENT_STATE_LABELS } from "../lib/constants";

const AGENT_STATE_ORDER: AgentState[] = [
  AgentState.NOT_STARTED,
  AgentState.RUNNING,
  AgentState.COMPLETED,
  AgentState.ERRORED,
];

const AGENT_STATE_BAR_COLORS: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "#E3E9F1",
  [AgentState.RUNNING]: "#F2A81E",
  [AgentState.COMPLETED]: "#18A673",
  [AgentState.ERRORED]: "#E23D3D",
};

const INSTANCE_STATUS_DOT_COLORS: Record<string, string> = {
  pending: "#8593A1",
  running: "#F2A81E",
  completed: "#18A673",
  failed: "#E23D3D",
  cancelled: "#8593A1",
};

interface AggregateStatsProps {
  instances: Array<{ status: InstanceStatus; agents: Array<{ state: AgentState }> }>;
}

export function AggregateStats({ instances }: AggregateStatsProps) {
  const byStatus = instances.reduce((acc, inst) => {
    acc[inst.status] = (acc[inst.status] || 0) + 1;
    return acc;
  }, {} as Record<InstanceStatus, number>);

  const byAgentState = instances.reduce((acc, inst) => {
    inst.agents.forEach((agent) => {
      acc[agent.state] = (acc[agent.state] || 0) + 1;
    });
    return acc;
  }, {} as Record<AgentState, number>);

  const totalAgents = Object.values(byAgentState).reduce((sum, count) => sum + count, 0);

  return (
    <div className="bg-white rounded-xl p-4 shadow-light-card border border-[#e2e8f0]">
      <h3 className="font-semibold text-[#12212F] mb-3">Aggregate stats</h3>

      <div className="mb-4">
        <h4 className="text-[13px] font-bold text-[#12212F] mb-2">
          Instance status
        </h4>
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          {Object.entries(byStatus).map(([status, count]) => (
            <span key={status} className="inline-flex items-center gap-1.5 text-xs text-[#62707E]">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: INSTANCE_STATUS_DOT_COLORS[status] ?? "#8593A1" }}
              />
              {status}:{" "}
              <span className="font-semibold text-[#12212F] tabular-nums">{count}</span>
            </span>
          ))}
        </div>
      </div>

      <div>
        <h4 className="text-[13px] font-bold text-[#12212F] mb-2">
          Agent states ({totalAgents} total)
        </h4>
        {totalAgents > 0 && (
          <div className="flex h-[10px] w-full overflow-hidden rounded-full mb-2 shadow-[inset_0_0_0_1px_rgba(16,32,48,.06)]">
            {AGENT_STATE_ORDER.map((state) => {
              const count = byAgentState[state] || 0;
              if (count === 0) return null;
              return (
                <div
                  key={state}
                  className="h-full transition-all duration-500"
                  style={{
                    width: `${(count / totalAgents) * 100}%`,
                    backgroundColor: AGENT_STATE_BAR_COLORS[state],
                  }}
                />
              );
            })}
          </div>
        )}
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          {Object.entries(byAgentState).map(([state, count]) => (
            <span key={state} className="inline-flex items-center gap-1.5 text-xs text-[#62707E]">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: AGENT_STATE_BAR_COLORS[state as AgentState] }}
              />
              {AGENT_STATE_LABELS[state as keyof typeof AGENT_STATE_LABELS]}:{" "}
              <span className="font-semibold text-[#12212F] tabular-nums">{count}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
