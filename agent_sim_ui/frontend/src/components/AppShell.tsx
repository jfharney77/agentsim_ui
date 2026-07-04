import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Globe, User, Plus } from "lucide-react";

export type NavTab = "setup" | "live" | "parallel" | "context";

interface AppShellProps {
  /** Which nav pill is highlighted, if any. */
  activeTab?: NavTab;
  /** Show the LIVE indicator + Cancel run button (running views only). */
  running?: boolean;
  /** Elapsed time (mm:ss) shown next to the LIVE dot. */
  elapsed?: string;
  onCancel?: () => void;
  children: ReactNode;
}

const TABS: { id: NavTab; label: string }[] = [
  { id: "setup", label: "Setup" },
  { id: "live", label: "Live Run" },
  { id: "parallel", label: "Parallel" },
  { id: "context", label: "Context" },
];

export function AppShell({
  activeTab,
  running = false,
  elapsed,
  onCancel,
  children,
}: AppShellProps) {
  const navigate = useNavigate();

  // From the calm front-door screens there is no active run yet, so the
  // run-scoped tabs fall back to Setup where a run is configured/launched.
  const routeFor: Record<NavTab, string> = {
    setup: "/setup",
    live: "/setup",
    parallel: "/parallel",
    context: "/setup",
  };

  return (
    <div className="min-h-screen bg-ink-bg text-[#E9EFF6] font-sans">
      {/* White utility bar (Dell pattern) */}
      <div className="flex items-center gap-[22px] px-[26px] py-[11px] bg-white border-b border-[#e6ebf1]">
        <div
          onClick={() => navigate("/")}
          className="flex items-center cursor-pointer flex-none"
        >
          <img
            src="/delllogo2.png"
            alt="Dell Technologies"
            className="h-[26px] w-auto"
          />
        </div>

        <div className="flex-1 max-w-[560px] flex items-center bg-white border border-[#cdd6e0] rounded-md overflow-hidden">
          <input
            type="text"
            placeholder="Search runs, instances, or agents"
            className="flex-1 min-w-0 border-none outline-none text-[13px] text-[#1B2733] px-3 py-[9px]"
          />
          <button
            type="button"
            className="border-none bg-[#f3f6fa] border-l border-[#e2e8f0] px-3 h-[34px] cursor-pointer flex items-center"
          >
            <Search className="w-4 h-4 text-dell" strokeWidth={2} />
          </button>
        </div>

        <div className="flex items-center gap-5 flex-none text-[13px] font-medium text-[#3d4a57]">
          <span className="hidden sm:flex items-center gap-1.5 cursor-pointer">
            <Globe className="w-[15px] h-[15px]" strokeWidth={1.7} />
            US/EN ▾
          </span>
          <span className="hidden sm:inline cursor-pointer">Docs</span>
          <span className="flex items-center gap-1.5 cursor-pointer">
            <User className="w-[15px] h-[15px]" strokeWidth={1.7} />
            Sign in ▾
          </span>
        </div>
      </div>

      {/* Dark app nav */}
      <div className="flex items-center justify-between px-[26px] py-[14px] border-b border-white/[.08] bg-gradient-to-b from-ink-navlo to-ink-bg">
        <div
          onClick={() => navigate("/")}
          className="flex items-center gap-[13px] cursor-pointer"
        >
          <div className="w-[34px] h-[34px] rounded-full border-2 border-dell bg-dell/[.14] flex items-center justify-center">
            <div className="w-2.5 h-2.5 rounded-full bg-dell" />
          </div>
          <div className="text-[15px] font-bold leading-none">AgentSim</div>
        </div>

        <div className="flex gap-[3px] bg-white/5 border border-white/[.09] rounded-[11px] p-1">
          {TABS.map((tab) => {
            const active = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => navigate(routeFor[tab.id])}
                className={`px-[15px] py-[7px] rounded-lg text-[13px] font-semibold transition-colors ${
                  active
                    ? "bg-dell text-white"
                    : "text-[#8AA0B8] hover:text-[#c6d5e5]"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-3">
          {running && (
            <div className="flex items-center gap-2">
              <span className="w-[9px] h-[9px] rounded-full bg-state-completed shadow-[0_0_8px_#18A673] animate-as-blink inline-block" />
              <span className="text-[12px] font-semibold text-[#dfe8f1]">
                LIVE
              </span>
              {elapsed && (
                <span className="text-[12px] font-medium text-[#8AA0B8]">
                  {elapsed}
                </span>
              )}
            </div>
          )}
          {running && (
            <button
              type="button"
              onClick={onCancel}
              className="text-[12px] font-semibold text-[#f28a8a] bg-transparent border border-state-errored/50 rounded-lg px-[15px] py-2 cursor-pointer"
            >
              Cancel run
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate("/setup")}
            className="flex items-center gap-1 text-[12px] font-semibold text-dell-soft bg-transparent border border-dell/[.55] rounded-lg px-[15px] py-2 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" strokeWidth={2.4} />
            New run
          </button>
        </div>
      </div>

      {children}
    </div>
  );
}
