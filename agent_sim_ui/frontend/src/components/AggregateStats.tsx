import { InstanceStatus, AgentState } from "../types/api";
import { AGENT_STATE_LABELS } from "../lib/constants";

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
            <span key={status} className="text-xs text-[#62707E]">
              {status}: <span className="font-semibold text-[#12212F]">{count}</span>
            </span>
          ))}
        </div>
      </div>

      <div>
        <h4 className="text-[13px] font-bold text-[#12212F] mb-2">
          Agent states ({totalAgents} total)
        </h4>
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          {Object.entries(byAgentState).map(([state, count]) => (
            <span key={state} className="text-xs text-[#62707E]">
              {AGENT_STATE_LABELS[state as keyof typeof AGENT_STATE_LABELS]}:{" "}
              <span className="font-semibold text-[#12212F]">{count}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
