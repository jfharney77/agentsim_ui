"""Writer worker -- LangGraph implementation for the orchestrator topology.

Same Agent Card and skill as the a2a/ version. The work runs through a LangGraph
StateGraph. The hub sees no difference -- the A2A transport is identical.
"""
from __future__ import annotations

import os

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from simulators.manual.orchestrator.brain import get_llm
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


def build_graph():
    llm = get_llm()

    def call_model(state: MessagesState):
        response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph.compile()


class GraphExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.graph = build_graph()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()
        result = self.graph.invoke({"messages": [HumanMessage(content=user_text)]})
        output = result["messages"][-1].content
        await event_queue.enqueue_event(new_agent_text_message(output))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancellation not supported")


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}/"
    card = AgentCard(
        name="Writer Worker",
        description="Writes the final briefing for the orchestrator.",
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[SKILL],
    )
    handler = DefaultRequestHandler(
        agent_executor=GraphExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(agent_card=card, http_handler=handler)
    print(f"[Writer Worker/LangGraph] listening on{url}")
    print(f"[Writer Worker/LangGraph] card at {url}.well-known/agent-card.json")
    uvicorn.run(app.build(), host=HOST, port=PORT, log_level="warning")
