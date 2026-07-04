import type { InstanceDescriptor } from "../types/api";
import { AgentState } from "../types/api";

/**
 * Live mesh graph for a single instance (design handoff — Live Run screen).
 *
 * The whole roster is always drawn: the first agent (Coordinator/Hub) sits at
 * the center and the rest spread evenly on a ring around it, so a dozen-agent
 * mesh is fully visible. Nodes are filled by agent state; "hot" edges (both
 * endpoints in scope, one running) animate a flowing dash. Out-of-scope
 * agents (``in_scope === false``) render as a dashed, muted circle labeled
 * OUT, their edges fade, and they are excluded from active/done tallies.
 */

// Hand-tuned positions for the classic ≤5-agent layout (viewBox 500×355):
// center, top, right, bottom, left — matches the design prototype exactly.
const POS5: readonly [number, number][] = [
  [250, 178],
  [250, 55],
  [402, 178],
  [250, 300],
  [98, 178],
];

/** Node positions for n agents: prototype layout up to 5, hub + ring beyond. */
function layoutPositions(n: number): [number, number][] {
  if (n <= POS5.length) return POS5.slice(0, n) as [number, number][];
  const cx = 250;
  const cy = 215;
  const radius = 155;
  const points: [number, number][] = [[cx, cy]];
  for (let i = 0; i < n - 1; i++) {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / (n - 1);
    points.push([cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]);
  }
  return points;
}

/** Spokes from the hub to every satellite, plus a ring between neighbors. */
function layoutEdges(n: number): [number, number][] {
  const edges: [number, number][] = [];
  for (let i = 1; i < n; i++) edges.push([0, i]);
  if (n > 3) {
    for (let i = 1; i < n; i++) edges.push([i, i === n - 1 ? 1 : i + 1]);
  } else if (n === 3) {
    edges.push([1, 2]);
  }
  return edges;
}

const NODE_FILL: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "#1C3454",
  [AgentState.RUNNING]: "#F2A81E",
  [AgentState.COMPLETED]: "#18A673",
  [AgentState.ERRORED]: "#E23D3D",
};

// Lighter center for each state's radial gradient (edge stays the state color).
const NODE_FILL_LIGHT: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "#33507C",
  [AgentState.RUNNING]: "#FFC65A",
  [AgentState.COMPLETED]: "#33C892",
  [AgentState.ERRORED]: "#F06B6B",
};

const GRADIENT_ID: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "as-mesh-grad-idle",
  [AgentState.RUNNING]: "as-mesh-grad-running",
  [AgentState.COMPLETED]: "as-mesh-grad-done",
  [AgentState.ERRORED]: "as-mesh-grad-err",
};

const GLOW_FILTER_ID = "as-mesh-glow-running";
const HOT_EDGE_GRADIENT_ID = "as-mesh-grad-hot-edge";
const HOT_ARROW_ID = "as-mesh-arrow-hot";
const NODE_WORD: Record<AgentState, string> = {
  [AgentState.NOT_STARTED]: "IDLE",
  [AgentState.RUNNING]: "RUN",
  [AgentState.COMPLETED]: "DONE",
  [AgentState.ERRORED]: "ERR",
};

const COLD_EDGE = "#33475F";
const NODE_STROKE = "#0A1727";
const IDLE_TEXT = "#8AA0B8";
const LABEL_FILL = "#C6D4E4";
const OUT_FILL = "#122237";
const OUT_STROKE = "#2A3E58";
const OUT_TEXT = "#4E637E";

export function LiveMesh({ instance }: { instance: InstanceDescriptor }) {
  // Backend emits agents in roster order; the whole mesh is always drawn.
  const nodes = instance.agents;
  const nCount = nodes.length;
  const POS = layoutPositions(nCount);
  const EDGES = layoutEdges(nCount);
  const inScope = (i: number) => nodes[i]?.in_scope !== false;
  const stateOf = (i: number) => nodes[i]?.state ?? AgentState.NOT_STARTED;

  return (
    <svg
      viewBox={nCount <= 5 ? "0 0 500 355" : "0 0 500 445"}
      style={{ width: "100%", maxWidth: 560, height: "auto", display: "block" }}
    >
      <defs>
        {(Object.keys(GRADIENT_ID) as AgentState[]).map((state) => (
          <radialGradient
            key={GRADIENT_ID[state]}
            id={GRADIENT_ID[state]}
            cx="38%"
            cy="32%"
            r="75%"
          >
            <stop offset="0%" stopColor={NODE_FILL_LIGHT[state]} />
            <stop offset="100%" stopColor={NODE_FILL[state]} />
          </radialGradient>
        ))}
        <filter id={GLOW_FILTER_ID} x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        {/* userSpaceOnUse: objectBoundingBox gradients vanish on perfectly
            vertical/horizontal <line>s (zero-area bbox). */}
        <linearGradient
          id={HOT_EDGE_GRADIENT_ID}
          gradientUnits="userSpaceOnUse"
          x1={0}
          y1={0}
          x2={500}
          y2={0}
        >
          <stop offset="0%" stopColor="#3B9BEA" />
          <stop offset="100%" stopColor="#7fb8e8" />
        </linearGradient>
        <marker
          id={HOT_ARROW_ID}
          markerWidth={6}
          markerHeight={6}
          viewBox="0 0 6 6"
          refX={5}
          refY={3}
          orient="auto"
          markerUnits="userSpaceOnUse"
        >
          <path d="M 0 0 L 6 3 L 0 6 Z" fill="#3B9BEA" />
        </marker>
      </defs>
      {EDGES.map(([ai, bi], k) => {
        if (ai >= nCount || bi >= nCount) return null;
        const a = POS[ai];
        const b = POS[bi];
        const bothIn = inScope(ai) && inScope(bi);
        const hot =
          bothIn &&
          (stateOf(ai) === AgentState.RUNNING ||
            stateOf(bi) === AgentState.RUNNING);
        // Ring edges (satellite→satellite) bow slightly outward via a
        // quadratic bezier; spokes from the hub stay straight.
        const isRing = ai !== 0 && bi !== 0;
        const edgeTransition = "opacity .4s ease, stroke .4s ease";
        const style = hot
          ? {
              animation: "as-edge-flow 0.9s linear infinite",
              opacity: 0.95,
              transition: edgeTransition,
            }
          : { opacity: bothIn ? 0.55 : 0.16, transition: edgeTransition };
        if (!isRing) {
          return (
            <line
              key={`e${k}`}
              x1={a[0]}
              y1={a[1]}
              x2={b[0]}
              y2={b[1]}
              stroke={hot ? `url(#${HOT_EDGE_GRADIENT_ID})` : COLD_EDGE}
              strokeWidth={hot ? 2.4 : 1.6}
              strokeDasharray="6 7"
              strokeLinecap="round"
              markerEnd={hot ? `url(#${HOT_ARROW_ID})` : undefined}
              style={style}
            />
          );
        }
        const mx = (a[0] + b[0]) / 2;
        const my = (a[1] + b[1]) / 2;
        const dx = b[0] - a[0];
        const dy = b[1] - a[1];
        const len = Math.hypot(dx, dy) || 1;
        // Small perpendicular bow, capped so short edges stay subtle.
        const bow = Math.min(14, len * 0.09);
        const cx = mx + (dy / len) * bow;
        const cy = my - (dx / len) * bow;
        return (
          <path
            key={`e${k}`}
            d={`M ${a[0]} ${a[1]} Q ${cx} ${cy} ${b[0]} ${b[1]}`}
            fill="none"
            stroke={hot ? `url(#${HOT_EDGE_GRADIENT_ID})` : COLD_EDGE}
            strokeWidth={hot ? 2.4 : 1.6}
            strokeDasharray="6 7"
            strokeLinecap="round"
            markerEnd={hot ? `url(#${HOT_ARROW_ID})` : undefined}
            style={style}
          />
        );
      })}
      {POS.map((p, n) => {
        if (n >= nCount) return null;
        const scoped = inScope(n);
        const state = stateOf(n);
        return (
          <g key={`n${n}`}>
            <title>
              {`${nodes[n]?.agent_name ?? ""} — ${
                scoped ? state : "out of scope"
              }`}
            </title>
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
              fill={scoped ? `url(#${GRADIENT_ID[state]})` : OUT_FILL}
              stroke={scoped ? NODE_STROKE : OUT_STROKE}
              strokeWidth={3}
              strokeDasharray={scoped ? undefined : "4 4"}
              style={{
                transition: "fill .4s ease",
                filter: !scoped
                  ? "none"
                  : state === AgentState.RUNNING
                  ? `url(#${GLOW_FILTER_ID})`
                  : "drop-shadow(0 2px 6px rgba(6,16,30,0.35))",
              }}
            />
            <text
              x={p[0]}
              y={p[1] + 4}
              textAnchor="middle"
              style={{
                font: "600 10.5px Roboto,sans-serif",
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
                font: "600 12px Roboto,sans-serif",
                fill: scoped ? LABEL_FILL : OUT_TEXT,
                transition: "fill .4s ease",
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
