"""Analyst agent -- LangGraph implementation.

Same Agent Card and skill as the a2a/ version. The work runs through a LangGraph
StateGraph instead of a direct Anthropic SDK call. Peers see no difference.
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

from simulators.manual.swarm.brain import get_llm
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
        name="Analyst",
        description="Turns raw research into risks, opportunities, and a fit assessment.",
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
    print(f"[Analyst/LangGraph] listening on {url}")
    print(f"[Analyst/LangGraph] card at {url}.well-known/agent-card.json")
    uvicorn.run(app.build(), host=HOST, port=PORT, log_level="warning")
