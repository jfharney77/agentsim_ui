export enum AgentState {
  NOT_STARTED = "not_started",
  RUNNING = "running",
  COMPLETED = "completed",
  ERRORED = "errored",
}

export enum InstanceStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
}

export interface AgentDescriptor {
  agent_id: string;
  agent_name: string;
  role: string;
  order: number;
}

export interface AgentRuntimeState {
  agent_id: string;
  agent_name: string;
  state: AgentState;
  /** False when the agent was excluded from the run via LaunchRequest.agent_scope. */
  in_scope: boolean;
  started_at: string | null;
  ended_at: string | null;
  failure_modes: string[];
  last_event: string | null;
}

export interface LaunchSpec {
  kind: string;
  command: string;
  args: string[];
  cwd: string;
  env_required: string[];
}

export interface Simulator {
  id: string;
  name: string;
  path: string;
  topology: string;
  launch: LaunchSpec;
  agents: AgentDescriptor[];
}

export interface LaunchRequest {
  simulator_id: string;
  concurrency: number;
  task_prompt?: string;
  /** Agent ids to run; omit or empty = whole mesh. Out-of-scope agents show as OUT. */
  agent_scope?: string[];
}

export interface InstanceDescriptor {
  instance_id: string;
  run_group_id: string;
  simulator_id: string;
  index: number;
  status: InstanceStatus;
  agents: AgentRuntimeState[];
}

export interface LaunchResponse {
  run_group_id: string;
  instances: InstanceDescriptor[];
}

export interface StateChangeEvent {
  instance_id: string;
  run_group_id: string;
  agent_id: string;
  agent_name: string;
  old_state: AgentState;
  new_state: AgentState;
  ts: string;
  failure_modes: string[];
}

export interface LogLine {
  ts: string;
  agent_id: string | null;
  level: string;
  message: string;
}

export interface RunLog {
  instance_id: string;
  simulator_id: string;
  created_at: string;
  lines: LogLine[];
}
