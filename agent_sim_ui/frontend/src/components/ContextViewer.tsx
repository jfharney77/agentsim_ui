import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { api } from "../lib/api";

interface ContextViewerProps {
  instanceId: string;
  agentId: string;
  agentName: string;
  onClose: () => void;
}

export function ContextViewer({ instanceId, agentId, agentName, onClose }: ContextViewerProps) {
  const [context, setContext] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getAgentContext(instanceId, agentId)
      .then(setContext)
      .catch((err: any) => setError(err.message))
      .finally(() => setLoading(false));
  }, [instanceId, agentId]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold">Context Window: {agentName}</h3>
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
            <div className="text-gray-600 dark:text-gray-400">Loading context...</div>
          )}
          {error && (
            <div className="text-red-600 dark:text-red-400">Error: {error}</div>
          )}
          {context && (
            <div className="space-y-4">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <p><strong>Model:</strong> {context.model}</p>
                <p><strong>Context Window:</strong> {context.context_window_tokens.toLocaleString()} tokens</p>
                <p><strong>Timestamp:</strong> {context.timestamp}</p>
                <p><strong>Tools:</strong> {context.tools.length > 0 ? context.tools.join(", ") : "None"}</p>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <p><strong>Messages:</strong> {context.messages.length}</p>
                <div className="mt-2 p-3 bg-gray-100 dark:bg-gray-900 rounded text-xs font-mono overflow-auto max-h-64">
                  <pre>{JSON.stringify(context.messages, null, 2)}</pre>
                </div>
              </div>
              <div className="text-xs text-yellow-600 dark:text-yellow-400 mt-4 p-3 bg-yellow-50 dark:bg-yellow-950 rounded">
                <strong>Note:</strong> Full context capture requires simulator instrumentation to capture LLM prompts/messages during runs. This is a placeholder implementation.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
