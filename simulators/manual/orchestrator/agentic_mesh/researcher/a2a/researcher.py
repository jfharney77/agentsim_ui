"""Research worker for the orchestrator topology."""
from __future__ import annotations

from a2a.types import AgentSkill

from simulators.manual.orchestrator.server import run_agent
from simulators.manual.orchestrator.ports import host_port

HOST, PORT = host_port("researcher")

SKILL = AgentSkill(
    id="research",
    name="Company research",
    description="Gathers raw factual background about a company or topic.",
    tags=["research", "facts", "background"],
    examples=["research Acme Corp", "what do we know about company X"],
)

SYSTEM_PROMPT = (
    "You are a Research worker in a hub-and-spoke multi-agent system. "
    "Given a company or topic, produce concise factual findings only. "
    "Output 5-8 short bullet points of facts, no analysis or recommendations."
)

if __name__ == "__main__":
    run_agent(
        name="Research Worker",
        description="Gathers raw factual background for the orchestrator.",
        host=HOST,
        port=PORT,
        skill=SKILL,
        system_prompt=SYSTEM_PROMPT,
    )
