import type { CSSProperties } from "react";
import type { InstanceStatus } from "../types/api";

interface CompactInstanceCellProps {
  index: number;
  status: InstanceStatus;
  agentStates: Record<string, string>;
  onClick: () => void;
}

type DominantState = "errored" | "running" | "completed" | "idle";

const CELL_COLORS: Record<DominantState, string> = {
  errored: "#E23D3D",
  running: "#F2A81E",
  completed: "#18A673",
  idle: "#E3E9F1",
};

export function CompactInstanceCell({ index, agentStates, onClick }: CompactInstanceCellProps) {
  const dominantState: DominantState = Object.values(agentStates).reduce<DominantState>((acc, state) => {
    if (state === "errored") return "errored";
    if (state === "running" && acc !== "errored") return "running";
    if (state === "completed" && acc !== "errored" && acc !== "running") return "completed";
    return acc;
  }, "idle");

  const style: CSSProperties = {
    backgroundColor: CELL_COLORS[dominantState],
    borderRadius: 5,
    border: dominantState === "idle" ? "1px solid #d7e2ee" : "1px solid transparent",
    transition: "background-color 0.3s ease, filter 0.3s ease, transform 0.15s ease",
  };

  if (dominantState === "running") {
    style.animation = "as-cell-pulse 1.3s ease-in-out infinite";
    style.filter = "drop-shadow(0 0 4px rgba(242, 168, 30, 0.45))";
  } else if (dominantState === "errored") {
    style.filter = "drop-shadow(0 0 4px rgba(226, 61, 61, 0.45))";
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-12 h-12 relative cursor-pointer transition-transform duration-150 hover:scale-125 hover:z-10 hover:ring-2 hover:ring-white/70 focus-visible:scale-125 focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:outline-none"
      style={style}
      title={`Instance #${index + 1} — ${dominantState}`}
      aria-label={`Instance #${index + 1} — ${dominantState}`}
    />
  );
}
