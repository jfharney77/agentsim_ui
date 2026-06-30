"""Researcher agent -- first peer in the swarm. Gathers raw facts."""
from __future__ import annotations

from a2a.types import AgentSkill

from simulators.manual.swarm.server import run_agent
from simulators.manual.swarm.ports import host_port

HOST, PORT = host_port("researcher")

SKILL = AgentSkill(
    id="research",
    name="Company research",
    description="Gathers raw factual background about a company or topic.",
    tags=["research", "facts", "background"],
    examples=["research Acme Corp", "what do we know about company X"],
)

SYSTEM_PROMPT = (
    "You are a Research agent in a multi-agent swarm. "
    "Given a company or topic, produce a concise, factual briefing of raw findings: "
    "what the entity does, its market, notable recent facts, and any obvious risks. "
    "Output 5-8 short bullet points of FACTS only -- no analysis, no recommendations. "
    "Another agent will analyze your output, so keep it clean and factual."
)

if __name__ == "__main__":
    run_agent(
        name="Researcher",
        description="Gathers raw factual background about a company or topic.",
        host=HOST,
        port=PORT,
        skill=SKILL,
        system_prompt=SYSTEM_PROMPT,
    )
