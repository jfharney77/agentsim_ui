import type { CSSProperties } from "react";
import { InstanceStatus } from "../types/api";

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

export function CompactInstanceCell({ index, status, agentStates, onClick }: CompactInstanceCellProps) {
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
    transition: "background-color 0.3s ease, box-shadow 0.3s ease",
  };

  if (dominantState === "running") {
    style.animation = "as-cell-pulse 1.3s ease-in-out infinite";
    style.boxShadow = "0 0 8px rgba(242, 168, 30, 0.45)";
  } else if (dominantState === "errored") {
    style.boxShadow = "0 0 8px rgba(226, 61, 61, 0.45)";
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-12 h-12"
      style={style}
      title={`Instance #${index + 1} - ${status}`}
    />
  );
}
