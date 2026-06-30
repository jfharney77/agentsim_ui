"""Run the same 3-role workflow through a central orchestrator hub.

Unlike the peer-to-peer swarm package, workers in this pattern do not call each
other directly. The hub discovers workers, validates skills, and dispatches each
step as a separate spoke call.
"""
from __future__ import annotations

import asyncio
import sys

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, create_text_message_object
from a2a.types import AgentCard, Message, Role
from simulators.manual.orchestrator.ports import base_url

WORKERS = {
    "researcher": {"base": base_url("researcher"), "expect_skill": "research"},
    "analyst": {"base": base_url("analyst"), "expect_skill": "analysis"},
    "writer": {"base": base_url("writer"), "expect_skill": "writing"},
}


async def discover(http: httpx.AsyncClient, base: str, expect_skill: str) -> AgentCard:
    resolver = A2ACardResolver(httpx_client=http, base_url=base)
    card = await resolver.get_agent_card()
    have = {s.id for s in card.skills}
    print(f"  discovered '{card.name}' at {base} -- skills: {sorted(have)}")
    if expect_skill not in have:
        raise RuntimeError(
            f"worker at {base} does not advertise required skill '{expect_skill}'"
        )
    return card


async def call_worker(factory: ClientFactory, card: AgentCard, text: str) -> str:
    client = factory.create(card)
    msg: Message = create_text_message_object(role=Role.user, content=text)

    result_text = ""
    async for event in client.send_message(msg):
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

        print("\n=== ORCHESTRATOR DISCOVERY (hub checks all workers) ===")
        cards = {
            role: await discover(http, cfg["base"], cfg["expect_skill"])
            for role, cfg in WORKERS.items()
        }

        print("\n=== HUB -> RESEARCH WORKER ===")
        facts = await call_worker(factory, cards["researcher"], f"Research: {topic}")
        print(facts)

        print("\n=== HUB -> ANALYSIS WORKER ===")
        analysis = await call_worker(
            factory, cards["analyst"], f"Analyze these findings:\n\n{facts}"
        )
        print(analysis)

        print("\n=== HUB -> WRITER WORKER ===")
        briefing = await call_worker(
            factory,
            cards["writer"],
            f"Write the final briefing from this analysis:\n\n{analysis}",
        )

        print("\n=== FINAL BRIEFING (hub collected writer artifact) ===")
        print(briefing)


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else (
        "Acme Corp, a mid-size industrial robotics manufacturer"
    )
    asyncio.run(run(topic))
