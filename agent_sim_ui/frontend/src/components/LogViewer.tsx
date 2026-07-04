import { X } from "lucide-react";
import type { RunLog } from "../types/api";

interface LogViewerProps {
  log: RunLog | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

function lineColor(message: string): string {
  if (/\bERROR\b|\bCRITICAL\b|\bFATAL\b/i.test(message)) return "#f26060";
  if (/\bWARN(ING)?\b/i.test(message)) return "#F2A81E";
  if (/\bINFO\b/i.test(message)) return "#c6d5e5";
  return "#8AA0B8";
}

export function LogViewer({ log, loading, error, onClose }: LogViewerProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div
        className="w-full max-w-4xl max-h-[80vh] flex flex-col rounded-xl border shadow-xl"
        style={{ backgroundColor: "#0D1E33", borderColor: "rgba(255,255,255,0.1)" }}
      >
        <div
          className="flex items-center justify-between px-4 py-2.5 border-b"
          style={{ borderColor: "rgba(255,255,255,0.1)" }}
        >
          <span className="font-bold" style={{ fontSize: 13, color: "#E9EFF6" }}>
            Log
          </span>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-white/10"
            style={{ color: "#8AA0B8" }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 max-h-[70vh] overflow-auto p-4">
          {loading && (
            <div style={{ color: "#8AA0B8", fontSize: 13 }}>Loading log...</div>
          )}
          {error && (
            <div style={{ color: "#f26060", fontSize: 13 }}>Error: {error}</div>
          )}
          {log && (
            <div className="font-mono" style={{ fontSize: 12, lineHeight: 1.6 }}>
              {log.lines.map((line, i) => (
                <div key={i} style={{ color: lineColor(line.message) }}>
                  <span style={{ color: "#6a7d92" }}>[{line.ts}]</span>
                  {line.agent_id && <span className="ml-2">[{line.agent_id}]</span>}
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
