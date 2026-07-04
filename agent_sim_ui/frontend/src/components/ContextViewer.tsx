import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { api } from "../lib/api";

interface ContextViewerProps {
  instanceId: string;
  agentId: string;
  agentName: string;
  onClose: () => void;
}

const ROLE_COLORS: Record<string, string> = {
  system: "#a78bfa",
  human: "#60a5fa",
  user: "#60a5fa",
  ai: "#34d399",
  assistant: "#34d399",
  tool: "#f59e0b",
};

function roleColor(role: string): string {
  return ROLE_COLORS[role.toLowerCase()] ?? "#8AA0B8";
}

function messageRole(msg: any): string {
  if (typeof msg?.role === "string") return msg.role;
  if (typeof msg?.type === "string") return msg.type;
  return "other";
}

function messageText(msg: any): string {
  const content = msg?.content;
  if (typeof content === "string") return content;
  return JSON.stringify(content ?? msg, null, 2);
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
    <div
      className="fixed inset-0 flex items-center justify-center z-50 p-4"
      style={{ background: "rgba(6,16,30,.74)" }}
    >
      <div
        className="rounded-[13px] border border-white/10 shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden"
        style={{ background: "#10233C" }}
      >
        <div style={{ height: 3, background: "#0076CE", flexShrink: 0 }} />
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <h3 className="text-[14px] font-bold" style={{ color: "#E9EFF6" }}>
            Context Window: {agentName}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded transition-colors"
            style={{ color: "#6a7d92" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "#E9EFF6"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "#6a7d92"; }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {loading && (
            <div className="text-[12px]" style={{ color: "#93a6ba" }}>Loading context...</div>
          )}
          {error && (
            <div className="text-[12px] text-red-400">Error: {error}</div>
          )}
          {context && (
            <div className="space-y-4">
              <div className="text-[12px] space-y-0.5" style={{ color: "#93a6ba" }}>
                <p><span style={{ color: "#E9EFF6" }}>Model:</span> {context.model}</p>
                <p><span style={{ color: "#E9EFF6" }}>Context Window:</span> {context.context_window_tokens.toLocaleString()} tokens</p>
                <p><span style={{ color: "#E9EFF6" }}>Timestamp:</span> {context.timestamp}</p>
                <p><span style={{ color: "#E9EFF6" }}>Tools:</span> {context.tools.length > 0 ? context.tools.join(", ") : "None"}</p>
                <p><span style={{ color: "#E9EFF6" }}>Messages:</span> {context.messages.length}</p>
              </div>

              <div className="space-y-3">
                {context.messages.map((msg: any, i: number) => (
                  <div key={i} className="flex flex-col gap-1">
                    <span
                      className="text-[12px] font-semibold lowercase"
                      style={{ color: roleColor(messageRole(msg)) }}
                    >
                      {messageRole(msg).toLowerCase()}
                    </span>
                    {typeof msg?.content === "string" ? (
                      <p className="text-[12px] whitespace-pre-wrap" style={{ color: "#93a6ba" }}>
                        {messageText(msg)}
                      </p>
                    ) : (
                      <div
                        className="p-3 rounded-lg text-[11px] font-mono overflow-auto max-h-64"
                        style={{ background: "#0A1728", color: "#93a6ba" }}
                      >
                        <pre>{messageText(msg)}</pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="text-[12px]" style={{ color: "#8AA0B8" }}>
                Note: full context capture requires simulator instrumentation to capture LLM prompts/messages during runs. This is a placeholder implementation.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
