import type { Simulator } from "../types/api";
import { Check } from "lucide-react";

interface SimulatorCardProps {
  simulator: Simulator;
  selected: boolean;
  onSelect: () => void;
}

export function SimulatorCard({ simulator, selected, onSelect }: SimulatorCardProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={`relative p-5 rounded-xl border-2 text-left transition-all shadow-sm ${
        selected
          ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
          : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
      }`}
    >
      {selected && (
        <div className="absolute top-3 right-3 p-1 bg-blue-500 rounded-full">
          <Check className="w-4 h-4 text-white" />
        </div>
      )}
      <h3 className="font-semibold text-lg mb-1">{simulator.name}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
        Topology: <span className="font-medium">{simulator.topology}</span>
      </p>
      <div className="text-sm text-gray-600 dark:text-gray-400">
        <span className="font-medium">Agents ({simulator.agents.length})</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {simulator.agents.map((agent) => (
          <span
            key={agent.agent_id}
            className="px-2 py-1 text-xs rounded-full bg-white/80 dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200"
          >
            {agent.agent_name}
          </span>
        ))}
      </div>
    </button>
  );
}
