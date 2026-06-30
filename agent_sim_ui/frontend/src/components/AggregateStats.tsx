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
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
      <h3 className="font-semibold mb-3">Aggregate Stats</h3>
      
      <div className="mb-4">
        <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Instance Status</h4>
        <div className="flex flex-wrap gap-2">
          {Object.entries(byStatus).map(([status, count]) => (
            <span key={status} className="px-2 py-1 rounded text-xs bg-gray-100 dark:bg-gray-700">
              {status}: {count}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Agent States ({totalAgents} total)</h4>
        <div className="flex flex-wrap gap-2">
          {Object.entries(byAgentState).map(([state, count]) => (
            <span key={state} className="px-2 py-1 rounded text-xs bg-gray-100 dark:bg-gray-700">
              {AGENT_STATE_LABELS[state as keyof typeof AGENT_STATE_LABELS]}: {count}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
