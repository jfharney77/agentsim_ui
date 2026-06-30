"""Analysis worker for the orchestrator topology."""
from __future__ import annotations

from a2a.types import AgentSkill

from simulators.manual.orchestrator.server import run_agent
from simulators.manual.orchestrator.ports import host_port

HOST, PORT = host_port("analyst")

SKILL = AgentSkill(
    id="analysis",
    name="Strategic analysis",
    description="Turns raw research facts into risks, opportunities, and a fit assessment.",
    tags=["analysis", "insight", "strategy"],
    examples=["analyze these findings", "what are the risks and opportunities"],
)

SYSTEM_PROMPT = (
    "You are an Analysis worker in a hub-and-spoke multi-agent system. "
    "Given factual findings, produce 2-3 opportunities, 2-3 risks, and one-line assessment. "
    "Use only facts provided; do not invent new facts."
)

if __name__ == "__main__":
    run_agent(
        name="Analysis Worker",
        description="Analyzes research for the orchestrator.",
        host=HOST,
        port=PORT,
        skill=SKILL,
        system_prompt=SYSTEM_PROMPT,
    )
