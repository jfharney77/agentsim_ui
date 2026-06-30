"""Writer worker for the orchestrator topology."""
from __future__ import annotations

from a2a.types import AgentSkill

from simulators.manual.orchestrator.server import run_agent
from simulators.manual.orchestrator.ports import host_port

HOST, PORT = host_port("writer")

SKILL = AgentSkill(
    id="writing",
    name="Briefing writer",
    description="Produces a polished, readable briefing from an analysis.",
    tags=["writing", "briefing", "summary"],
    examples=["write up this analysis", "produce the final briefing"],
)

SYSTEM_PROMPT = (
    "You are a Writer worker in a hub-and-spoke multi-agent system. "
    "Given a strategic analysis, produce one paragraph summary, short opportunities bullets, "
    "short risks bullets, and one bottom-line sentence."
)

if __name__ == "__main__":
    run_agent(
        name="Writer Worker",
        description="Writes the final briefing for the orchestrator.",
        host=HOST,
        port=PORT,
        skill=SKILL,
        system_prompt=SYSTEM_PROMPT,
    )
