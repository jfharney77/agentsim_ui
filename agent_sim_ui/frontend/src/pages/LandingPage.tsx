import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  Mic,
  ArrowRight,
  LayoutGrid,
  Activity,
  Eye,
  Columns,
  FileText,
} from "lucide-react";
import { api } from "../lib/api";
import { AppShell } from "../components/AppShell";

const TASK_MAX = 200;

// Front-door decoration; the app has no run-history endpoint yet.
const RECENT_RUNS = [
  { id: "#037", sim: "Swarm", n: 100, ago: "2m ago", status: "running" },
  { id: "#036", sim: "Orchestrator", n: 10, ago: "18m ago", status: "done" },
  { id: "#034", sim: "ChatDev", n: 5, ago: "1h ago", status: "done" },
  { id: "#031", sim: "MetaGPT", n: 1, ago: "3h ago", status: "error" },
];

const PILLS = [
  { label: "New Swarm run", to: "/setup" },
  { label: "Watch live mesh", to: "/setup" },
  { label: "Run at scale", to: "/parallel" },
  { label: "Inspect context", to: "/setup" },
];

const NAV_CARDS = [
  {
    glyph: <Activity className="w-5 h-5" />,
    title: "Live Run",
    desc: "Follow one run's agents as they message across the mesh in real time.",
    to: "/setup",
  },
  {
    glyph: <LayoutGrid className="w-5 h-5" />,
    title: "Parallel",
    desc: "Run hundreds or thousands at once and spot failures at a glance.",
    to: "/parallel",
  },
  {
    glyph: <Eye className="w-5 h-5" />,
    title: "Context",
    desc: "Compare each agent's context window — tokens, tool calls, free space.",
    to: "/setup",
  },
];

const QUICK_LINKS = [
  { icon: <LayoutGrid className="w-[17px] h-[17px]" />, label: "Browse simulators", to: "/setup", highlight: true },
  { icon: <Activity className="w-[17px] h-[17px]" />, label: "Detect active runs", to: "/setup", highlight: false },
  { icon: <Eye className="w-[17px] h-[17px]" />, label: "Recently viewed", to: "/parallel", highlight: false },
  { icon: <Columns className="w-[17px] h-[17px]" />, label: "Context workspace", to: "/setup", highlight: false },
  { icon: <FileText className="w-[17px] h-[17px]" />, label: "Docs & API", to: null, highlight: false },
];

// Plain colored status words — no highlight boxes (Dell clean design).
function statusColor(status: string) {
  const map: Record<string, string> = {
    running: "text-state-running",
    done: "text-state-completed",
    error: "text-state-errored",
  };
  return map[status] || "text-[#8AA0B8]";
}

// Hex for the small state dot preceding each status word.
function statusDotHex(status: string) {
  const map: Record<string, string> = {
    running: "#F2A81E",
    done: "#18A673",
    error: "#E23D3D",
  };
  return map[status] || "#8AA0B8";
}

export function LandingPage() {
  const navigate = useNavigate();
  const [task, setTask] = useState("");
  const [simCount, setSimCount] = useState<number | null>(null);

  useEffect(() => {
    api
      .listSimulators()
      .then((sims) => setSimCount(sims.length))
      .catch(() => setSimCount(null));
  }, []);

  const submitTask = () => {
    navigate("/setup", { state: { task } });
  };

  return (
    <AppShell>
      {/* Dark hero */}
      <div className="relative px-[26px] pt-[clamp(32px,6vw,58px)] pb-[54px]">
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none [background:radial-gradient(600px_300px_at_50%_30%,rgba(0,118,206,.18),transparent_70%)]"
        />
        <div className="relative max-w-[1060px] mx-auto">
          <div className="text-center mb-11">
            <h1 className="text-[clamp(32px,4.6vw,46px)] leading-[1.15] font-light mb-4">
              Watch agents think, at any scale.
            </h1>
            <p className="text-[clamp(14px,1.6vw,16px)] leading-[1.6] text-[#8AA0B8] max-w-[640px] mx-auto mb-7">
              Launch multi-agent simulators, follow the mesh as it passes
              messages, and inspect every agent's context window — from a single
              run to a thousand in parallel.
            </p>

            {/* Ask box */}
            <div className="max-w-[780px] mx-auto text-left">
              <div className="bg-white rounded-[18px] px-5 pt-[18px] pb-[14px] shadow-ask transition-shadow focus-within:shadow-[0_14px_44px_rgba(0,0,0,.38),0_0_0_2px_rgba(0,118,206,.35)]">
                <div className="flex items-start gap-[11px] min-h-[64px]">
                  <Sparkles className="w-[18px] h-[18px] mt-0.5 text-[#7b5cf0] flex-none" />
                  <input
                    type="text"
                    value={task}
                    maxLength={TASK_MAX}
                    onChange={(e) => setTask(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submitTask()}
                    placeholder='Describe a run to launch — e.g. "Swarm, 100 instances, analyze Acme Corp market position"'
                    className="flex-1 border-none outline-none text-[15px] text-[#1B2733] bg-transparent pt-px"
                  />
                </div>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[12px] text-[#9aa7b4]">
                    {task.length}/{TASK_MAX}
                  </span>
                  <div className="flex items-center gap-3.5">
                    <Mic className="w-4 h-4 text-[#6b7785]" strokeWidth={2} />
                    <button
                      type="button"
                      onClick={submitTask}
                      className="w-[38px] h-[38px] rounded-full border-none text-white flex items-center justify-center cursor-pointer bg-[linear-gradient(135deg,#5b8def,#a86ad6,#e59ac0)] transition-transform hover:scale-105"
                    >
                      <ArrowRight className="w-[18px] h-[18px]" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Gradient-border pills */}
              <div className="flex gap-3 justify-center mt-[18px] flex-wrap">
                {PILLS.map((pill) => (
                  <button
                    key={pill.label}
                    type="button"
                    onClick={() => navigate(pill.to)}
                    className="whitespace-nowrap text-white text-[13px] font-semibold px-5 py-[11px] rounded-full cursor-pointer border-[1.6px] border-transparent [background:linear-gradient(#0A1727,#0A1727)_padding-box,linear-gradient(95deg,#2E93E6,#a24fd0)_border-box] transition-[filter,transform] hover:brightness-110 active:scale-[.98]"
                  >
                    {pill.label}
                  </button>
                ))}
              </div>

              <div className="text-center mt-3.5 text-[12px] text-[#5f7da0]">
                Runs consume tokens.{" "}
                <span className="text-dell-soft underline cursor-pointer">
                  Provider settings
                </span>
              </div>
            </div>
          </div>

          {/* Light content band */}
          <div className="bg-band rounded-[18px] px-7 pt-[26px] pb-7">
            <div className="flex items-baseline justify-between mb-5">
              <div className="text-[clamp(20px,2.4vw,24px)] font-normal text-[#12212F]">
                Jump back in
              </div>
              <span className="text-[12px] text-[#62707E]">
                {simCount ?? 5} simulators · 1 run active · anthropic
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-[22px] items-start">
              {/* Left: nav cards + recent runs */}
              <div className="min-w-0">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 mb-4">
                  {NAV_CARDS.map((card) => (
                    <button
                      key={card.title}
                      type="button"
                      onClick={() => navigate(card.to)}
                      className="group text-left bg-white border border-[#e2e8f0] rounded-xl p-[18px] cursor-pointer transition-all duration-200 active:scale-[.99] hover:border-dell hover:-translate-y-0.5 hover:shadow-[0_6px_18px_rgba(16,32,48,.08)]"
                    >
                      <div className="text-dell mb-3 transition-transform group-hover:scale-110">{card.glyph}</div>
                      <div className="text-[15px] font-bold text-[#12212F] mb-1.5">
                        {card.title}
                      </div>
                      <div className="text-[12px] leading-[1.55] text-[#62707E] mb-3">
                        {card.desc}
                      </div>
                      <div className="text-[12px] font-semibold text-dell">
                        Open{" "}
                        <span className="inline-block transition-transform group-hover:translate-x-0.5">
                          →
                        </span>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="bg-white border border-[#e2e8f0] rounded-xl px-[18px] py-4">
                  <div className="text-[13px] font-bold text-[#12212F] mb-1">
                    Recent runs
                  </div>
                  {RECENT_RUNS.map((run) => (
                    <div
                      key={run.id}
                      className="grid grid-cols-[82px_1fr_auto_auto] gap-3.5 items-center py-2.5 border-t border-[#eef2f7] hover:bg-[#fafbfd] transition-colors rounded"
                    >
                      <span className="text-[12px] font-medium text-dell">
                        {run.id}
                      </span>
                      <span className="text-[12px] font-medium text-[#4A5765] tabular-nums">
                        {run.sim} · {run.n}×
                      </span>
                      <span className="text-[11px] text-[#8593A1]">
                        {run.ago}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span
                          className={`w-2 h-2 rounded-full ${run.status === "running" ? "animate-as-blink" : ""}`}
                          style={{ background: statusDotHex(run.status) }}
                        />
                        <span
                          className={`text-[11px] font-semibold ${statusColor(run.status)}`}
                        >
                          {run.status}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: blue icon rail */}
              <div>
                <div className="text-[13px] font-bold text-[#12212F] mb-[11px]">
                  Quick links
                </div>
                {QUICK_LINKS.map((link) => (
                  <button
                    key={link.label}
                    type="button"
                    onClick={() => link.to && navigate(link.to)}
                    className={`flex items-center gap-[11px] w-full text-left rounded-lg px-3.5 py-3 cursor-pointer mb-[9px] transition-all active:scale-[.99] focus-visible:ring-2 focus-visible:ring-dell/40 hover:border-dell hover:translate-x-0.5 ${
                      link.highlight
                        ? "bg-[#EAF3FB] border border-[#cfe4f5] hover:bg-[#DDEEFB]"
                        : "bg-white border border-[#d7e2ee]"
                    }`}
                  >
                    <span className="text-dell flex-none">{link.icon}</span>
                    <span className="text-[13px] font-semibold text-dell">
                      {link.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
