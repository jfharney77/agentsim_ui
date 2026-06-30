import { X } from "lucide-react";
import type { RunLog } from "../types/api";

interface LogViewerProps {
  log: RunLog | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export function LogViewer({ log, loading, error, onClose }: LogViewerProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold">Instance Log</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {loading && (
            <div className="text-gray-600 dark:text-gray-400">Loading log...</div>
          )}
          {error && (
            <div className="text-red-600 dark:text-red-400">Error: {error}</div>
          )}
          {log && (
            <div className="font-mono text-sm space-y-1">
              {log.lines.map((line, i) => (
                <div key={i} className="text-gray-700 dark:text-gray-300">
                  <span className="text-gray-500 dark:text-gray-500">[{line.ts}]</span>
                  {line.agent_id && <span className="text-blue-600 dark:text-blue-400 ml-2">[{line.agent_id}]</span>}
                  <span className="ml-2">{line.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
