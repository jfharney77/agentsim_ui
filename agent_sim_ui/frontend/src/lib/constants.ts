import { AgentState } from "../types/api";

/** Agent-state fill colors (design handoff — tweakable theme constants). */
export const AGENT_STATE_COLORS: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "#E3E9F1",
  [AgentState.RUNNING]: "#F2A81E",
  [AgentState.COMPLETED]: "#18A673",
  [AgentState.ERRORED]: "#E23D3D",
};

/** Human-readable labels for each agent state. */
export const AGENT_STATE_LABELS: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "Not started",
  [AgentState.RUNNING]: "Running",
  [AgentState.COMPLETED]: "Completed",
  [AgentState.ERRORED]: "Errored",
};
