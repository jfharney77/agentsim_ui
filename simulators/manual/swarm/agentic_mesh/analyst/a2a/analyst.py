"""Analyst agent -- second peer. Turns raw facts into insight."""
from __future__ import annotations

from a2a.types import AgentSkill

from simulators.manual.swarm.server import run_agent
from simulators.manual.swarm.ports import host_port

HOST, PORT = host_port("analyst")

SKILL = AgentSkill(
    id="analysis",
    name="Strategic analysis",
    description="Turns raw research facts into risks, opportunities, and a fit assessment.",
    tags=["analysis", "insight", "strategy"],
    examples=["analyze these findings", "what are the risks and opportunities"],
)

SYSTEM_PROMPT = (
    "You are an Analysis agent in a multi-agent swarm. "
    "You receive raw factual findings from a research agent. "
    "Produce a short structured analysis: 2-3 key opportunities, 2-3 key risks, "
    "and a one-line overall assessment. "
    "Reason from the facts you were given; do not invent new facts. "
    "A writer agent will turn your analysis into a final briefing."
)

if __name__ == "__main__":
    run_agent(
        name="Analyst",
        description="Turns raw research into risks, opportunities, and a fit assessment.",
        host=HOST,
        port=PORT,
        skill=SKILL,
        system_prompt=SYSTEM_PROMPT,
    )
