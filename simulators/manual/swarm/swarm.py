"""Run the 3-agent swarm end to end.

This is the 'swarm' itself: there is no orchestrator agent. The handoff order
(researcher -> analyst -> writer) is the swarm's wiring, and each step is a real
A2A call:
    1. DISCOVER  -- fetch the peer's Agent Card from its /.well-known URL
    2. INSPECT   -- confirm the card advertises the skill we need
    3. SEND      -- message/send the work, receive the result message

Usage:
    python -m swarm.swarm "Acme Corp, a mid-size industrial robotics maker"
"""
from __future__ import annotations

import asyncio
import sys

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, create_text_message_object
from a2a.types import AgentCard, Message, Role
from simulators.manual.swarm.ports import base_url

# The swarm's fixed topology: who lives where, and which skill we expect there.
PEERS = {
    "researcher": {"base": base_url("researcher"), "expect_skill": "research"},
    "analyst": {"base": base_url("analyst"), "expect_skill": "analysis"},
    "writer": {"base": base_url("writer"), "expect_skill": "writing"},
}


async def discover(http: httpx.AsyncClient, base: str, expect_skill: str) -> AgentCard:
    """Fetch and validate a peer's Agent Card (steps 1 + 2)."""
    resolver = A2ACardResolver(httpx_client=http, base_url=base)
    card = await resolver.get_agent_card()
    have = {s.id for s in card.skills}
    print(f"  discovered '{card.name}' at {base} -- skills: {sorted(have)}")
    if expect_skill not in have:
        raise RuntimeError(
            f"peer at {base} does not advertise required skill '{expect_skill}'"
        )
    return card


async def call_peer(factory: ClientFactory, card: AgentCard, text: str) -> str:
    """Send work to a peer and return its result text (step 3)."""
    client = factory.create(card)
    msg: Message = create_text_message_object(role=Role.user, content=text)

    result_text = ""
    async for event in client.send_message(msg):
        # send_message yields either a Message or a (Task, update) tuple.
        if isinstance(event, Message):
            result_text = "".join(
                p.root.text for p in event.parts if p.root.kind == "text"
            )
        else:
            task, _update = event
            if task.artifacts:
                for artifact in task.artifacts:
                    for p in artifact.parts:
                        if p.root.kind == "text":
                            result_text = p.root.text
    return result_text.strip()


async def run(topic: str) -> None:
    async with httpx.AsyncClient(timeout=60) as http:
        factory = ClientFactory(ClientConfig(httpx_client=http, streaming=False))

        print("\n=== DISCOVERY (each peer's card fetched over HTTP) ===")
        cards = {
            role: await discover(http, cfg["base"], cfg["expect_skill"])
            for role, cfg in PEERS.items()
        }

        print("\n=== HANDOFF 1: client -> Researcher ===")
        facts = await call_peer(factory, cards["researcher"], f"Research: {topic}")
        print(facts)

        print("\n=== HANDOFF 2: Researcher output -> Analyst ===")
        analysis = await call_peer(
            factory, cards["analyst"], f"Analyze these findings:\n\n{facts}"
        )
        print(analysis)

        print("\n=== HANDOFF 3: Analyst output -> Writer ===")
        briefing = await call_peer(
            factory, cards["writer"], f"Write the final briefing from this analysis:\n\n{analysis}"
        )

        print("\n=== FINAL BRIEFING (Writer's artifact) ===")
        print(briefing)


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else (
        "Acme Corp, a mid-size industrial robotics manufacturer"
    )
    asyncio.run(run(topic))
