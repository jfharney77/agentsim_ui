"""Turn a 'role' (name, skill, system prompt) into a real A2A HTTP server.

Every agent in the swarm is built with this one factory, so the A2A mechanics
live in exactly one place. Each server:
  * publishes its own Agent Card at /.well-known/agent-card.json
  * exposes a JSON-RPC endpoint that accepts message/send
  * does its work via the shared LLM brain, then returns a text artifact
"""
from __future__ import annotations

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from a2a.utils import new_agent_text_message

from .brain import think


def build_card(*, name: str, description: str, url: str, skill: AgentSkill) -> AgentCard:
    """Construct the public Agent Card -- the contract this agent advertises."""
    return AgentCard(
        name=name,
        description=description,
        url=url,                       # where this agent's JSON-RPC endpoint lives
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


class RoleExecutor(AgentExecutor):
    """Bridges the A2A protocol to one role's LLM logic.

    The SDK calls execute() for every inbound message/send. We pull the caller's
    text, run the role's system prompt against it, and enqueue a single agent
    message back. That message is what the calling peer receives as the result.
    """

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()
        result = think(self.system_prompt, user_text)
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # This demo's work is a single synchronous LLM turn -- nothing to cancel.
        raise NotImplementedError("cancellation is not supported in this demo")


def run_agent(
    *,
    name: str,
    description: str,
    host: str,
    port: int,
    skill: AgentSkill,
    system_prompt: str,
) -> None:
    """Start one agent as a blocking Uvicorn server."""
    url = f"http://{host}:{port}/"
    card = build_card(name=name, description=description, url=url, skill=skill)

    handler = DefaultRequestHandler(
        agent_executor=RoleExecutor(system_prompt),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(agent_card=card, http_handler=handler)

    print(f"[{name}] listening on {url}")
    print(f"[{name}] card at {url}.well-known/agent-card.json")
    uvicorn.run(app.build(), host=host, port=port, log_level="warning")
