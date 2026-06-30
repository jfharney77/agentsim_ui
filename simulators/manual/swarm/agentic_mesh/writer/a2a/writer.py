"""Writer agent -- third peer. Produces the final briefing document."""
from __future__ import annotations

from a2a.types import AgentSkill

from simulators.manual.swarm.server import run_agent
from simulators.manual.swarm.ports import host_port

HOST, PORT = host_port("writer")

SKILL = AgentSkill(
    id="writing",
    name="Briefing writer",
    description="Produces a polished, readable briefing from an analysis.",
    tags=["writing", "briefing", "summary"],
    examples=["write up this analysis", "produce the final briefing"],
)

SYSTEM_PROMPT = (
    "You are a Writer agent in a multi-agent swarm. "
    "You receive a strategic analysis and turn it into a final briefing for a busy reader. "
    "Write a tight briefing: a one-paragraph summary, then 'Opportunities' and 'Risks' "
    "sections as short bullets, then a single 'Bottom line' sentence. "
    "Be clear and concrete. This is the final deliverable -- no further agent edits it."
)

if __name__ == "__main__":
    run_agent(
        name="Writer",
        description="Produces a polished briefing from an analysis.",
        host=HOST,
        port=PORT,
        skill=SKILL,
        system_prompt=SYSTEM_PROMPT,
    )
