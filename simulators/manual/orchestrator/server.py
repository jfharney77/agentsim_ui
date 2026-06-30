"""Create role workers for the hub-and-spoke orchestrator pattern."""
from __future__ import annotations

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from .brain import think


def build_card(*, name: str, description: str, url: str, skill: AgentSkill) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


class RoleExecutor(AgentExecutor):
    """Worker executor that handles one request at a time."""

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()
        result = think(self.system_prompt, user_text)
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
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
