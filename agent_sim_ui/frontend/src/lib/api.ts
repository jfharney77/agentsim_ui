import type {
  Simulator,
  LaunchRequest,
  LaunchResponse,
  InstanceDescriptor,
  StateChangeEvent,
  RunLog,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

interface GroupSnapshot {
  run_group_id: string;
  instances: InstanceDescriptor[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listSimulators(): Promise<Simulator[]> {
    return request<Simulator[]>("/simulators");
  },

  launch(body: LaunchRequest): Promise<LaunchResponse> {
    return request<LaunchResponse>("/launch", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getRun(runGroupId: string): Promise<GroupSnapshot> {
    return request<GroupSnapshot>(`/runs/${runGroupId}`);
  },

  cancelRun(runGroupId: string): Promise<{ run_group_id: string }> {
    return request(`/runs/${runGroupId}/cancel`, { method: "POST" });
  },

  getInstanceLog(instanceId: string): Promise<RunLog> {
    return request<RunLog>(`/instances/${instanceId}/log`);
  },

  getAgentContext(instanceId: string, agentId: string): Promise<unknown> {
    return request(`/instances/${instanceId}/agents/${agentId}/context`);
  },

  /**
   * Subscribe to the SSE stream of StateChangeEvents for a run group.
   * Returns a cleanup function that closes the underlying EventSource.
   */
  streamEvents(
    runGroupId: string,
    onEvent: (event: StateChangeEvent) => void,
    onError?: (err: unknown) => void
  ): () => void {
    const source = new EventSource(`${BASE_URL}/runs/${runGroupId}/events`);
    source.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data) as StateChangeEvent);
      } catch (err) {
        onError?.(err);
      }
    };
    source.onerror = (err) => {
      onError?.(err);
    };
    return () => source.close();
  },
};
