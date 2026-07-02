import type { InstanceDescriptor } from "../types/api";
import { AgentState } from "../types/api";

/**
 * Live mesh graph for a single instance (design handoff — Live Run screen).
 *
 * Up to five nodes are placed on a fixed layout (Coordinator/Hub center, the
 * rest around it) and labeled with the instance's agent roster. Nodes are
 * filled by agent state; "hot" edges (both endpoints in scope, one running)
 * animate a flowing dash. Out-of-scope agents (``in_scope === false``) render
 * as a dashed, muted circle labeled OUT, their edges fade, and they are
 * excluded from active/done tallies.
 */

// Fixed node positions (viewBox 0 0 500 355): center, top, right, bottom, left.
const POS: readonly [number, number][] = [
  [250, 178],
  [250, 55],
  [402, 178],
  [250, 300],
  [98, 178],
];
const EDGES: readonly [number, number][] = [
  [0, 1],
  [0, 2],
  [0, 3],
  [0, 4],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 1],
];

const NODE_FILL: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "#1C3454",
  [AgentState.RUNNING]: "#F2A81E",
  [AgentState.COMPLETED]: "#18A673",
  [AgentState.ERRORED]: "#E23D3D",
};
const NODE_WORD: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "IDLE",
  [AgentState.RUNNING]: "RUN",
  [AgentState.COMPLETED]: "DONE",
  [AgentState.ERRORED]: "ERR",
};

const COLD_EDGE = "#33475F";
const HOT_EDGE = "#3B9BEA";
const NODE_STROKE = "#0A1727";
const IDLE_TEXT = "#8AA0B8";
const LABEL_FILL = "#C6D4E4";
const OUT_FILL = "#122237";
const OUT_STROKE = "#2A3E58";
const OUT_TEXT = "#4E637E";

export function LiveMesh({ instance }: { instance: InstanceDescriptor }) {
  // Backend emits agents in roster order; only the first five map onto the layout.
  const nodes = instance.agents.slice(0, POS.length);
  const nCount = Math.min(POS.length, nodes.length);
  const inScope = (i: number) => nodes[i]?.in_scope !== false;
  const stateOf = (i: number) => nodes[i]?.state ?? AgentState.NOT_STARTED;

  return (
    <svg
      viewBox="0 0 500 355"
      style={{ width: "100%", maxWidth: 560, height: "auto", display: "block" }}
    >
      {EDGES.map(([ai, bi], k) => {
        if (ai >= nCount || bi >= nCount) return null;
        const a = POS[ai];
        const b = POS[bi];
        const bothIn = inScope(ai) && inScope(bi);
        const hot =
          bothIn &&
          (stateOf(ai) === AgentState.RUNNING ||
            stateOf(bi) === AgentState.RUNNING);
        return (
          <line
            key={`e${k}`}
            x1={a[0]}
            y1={a[1]}
            x2={b[0]}
            y2={b[1]}
            stroke={hot ? HOT_EDGE : COLD_EDGE}
            strokeWidth={hot ? 2.4 : 1.6}
            strokeDasharray="6 7"
            strokeLinecap="round"
            style={
              hot
                ? { animation: "as-edge-flow 0.9s linear infinite", opacity: 0.95 }
                : { opacity: bothIn ? 0.55 : 0.16 }
            }
          />
        );
      })}
      {POS.map((p, n) => {
        if (n >= nCount) return null;
        const scoped = inScope(n);
        const state = stateOf(n);
        return (
          <g key={`n${n}`}>
            {scoped && state === AgentState.RUNNING && (
              <circle
                cx={p[0]}
                cy={p[1]}
                r={29}
                fill="none"
                stroke={NODE_FILL[AgentState.RUNNING]}
                strokeWidth={2}
                style={{
                  transformBox: "fill-box",
                  transformOrigin: "center",
                  animation: "as-ping 1.6s ease-out infinite",
                }}
              />
            )}
            <circle
              cx={p[0]}
              cy={p[1]}
              r={28}
              fill={scoped ? NODE_FILL[state] : OUT_FILL}
              stroke={scoped ? NODE_STROKE : OUT_STROKE}
              strokeWidth={3}
              strokeDasharray={scoped ? undefined : "4 4"}
              style={{
                filter: scoped
                  ? "drop-shadow(0 2px 6px rgba(6,16,30,0.35))"
                  : "none",
              }}
            />
            <text
              x={p[0]}
              y={p[1] + 4}
              textAnchor="middle"
              style={{
                font: "600 10.5px 'Hanken Grotesk',sans-serif",
                fill: !scoped
                  ? OUT_TEXT
                  : state === AgentState.NOT_STARTED
                  ? IDLE_TEXT
                  : "#ffffff",
              }}
            >
              {scoped ? NODE_WORD[state] : "OUT"}
            </text>
            <text
              x={p[0]}
              y={p[1] + 47}
              textAnchor="middle"
              style={{
                font: "600 12px 'Hanken Grotesk',sans-serif",
                fill: scoped ? LABEL_FILL : OUT_TEXT,
              }}
            >
              {nodes[n]?.agent_name ?? ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
