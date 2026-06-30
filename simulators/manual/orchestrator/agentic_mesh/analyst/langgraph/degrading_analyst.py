"""Degrading Analyst — LangGraph implementation for the orchestrator topology.

Same Agent Card and skill as the normal orchestrator analyst. The hub sees no
difference — the A2A transport is identical.
"""
from __future__ import annotations

import json
import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from simulators.manual.orchestrator.degrading_brain import DegradationState, degrading_think
from simulators.manual.orchestrator.ports import host_port

HOST, PORT = host_port("analyst")

SKILL = AgentSkill(
    id="analysis",
    name="Strategic analysis",
    description=(
        "Turns raw research facts into risks, opportunities, "
        "and a fit assessment."
    ),
    tags=["analysis", "insight", "strategy"],
    examples=["analyze these findings", "what are the risks and opportunities"],
)

SYSTEM_PROMPT = (
    "You are an Analysis worker in a hub-and-spoke multi-agent system. "
    "Given factual findings, produce 2-3 opportunities, 2-3 risks, "
    "and one-line assessment. Use only facts provided; do not invent new facts."
)

_degradation_state = DegradationState()


def build_graph():
    def degrading_node(state: MessagesState):
        user_text = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_text = msg.content
                break

        result = degrading_think(
            SYSTEM_PROMPT, user_text, _degradation_state
        )

        # Export telemetry data after each call
        telemetry_data = {
            "call": _degradation_state.call_count,
            "level": _degradation_state.degradation_level,
            "active": len(_degradation_state.active_failures),
            "severity": _degradation_state.total_severity,
            "cumulative": _degradation_state.cumulative_severity,
            "critical_cycles": _degradation_state.cycles_in_critical,
            "failures": _degradation_state.active_failures.copy()
        }
        
        # Append to telemetry file
        with open("degradation_telemetry.json", "a") as f:
            f.write(json.dumps(telemetry_data) + "\n")

        # Log terminal state for monitoring systems
        if _degradation_state.is_terminal:
            print(f"  [DEGRADING ANALYST] ☠ Agent has reached terminal state")
            print(f"  [DEGRADING ANALYST] Reason: {_degradation_state.terminal_reason}")
            print(f"  [DEGRADING ANALYST] Total calls before death: {_degradation_state.call_count}")

        return {"messages": [AIMessage(content=result)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", degrading_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph.compile()


class DegradingGraphExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.graph = build_graph()

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        user_text = context.get_user_input()
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=user_text)]}
        )
        output = result["messages"][-1].content
        await event_queue.enqueue_event(new_agent_text_message(output))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError("cancellation not supported")


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}/"
    card = AgentCard(
        name="Degrading Analysis Worker",
        description=(
            "An analysis worker that progressively degrades, "
            "simulating MAST taxonomy failure modes. LangGraph implementation."
        ),
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[SKILL],
    )
    handler = DefaultRequestHandler(
        agent_executor=DegradingGraphExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(agent_card=card, http_handler=handler)
    print(f"[Degrading Analysis Worker/LangGraph] listening on {url}")
    print(f"[Degrading Analysis Worker/LangGraph] card at {url}.well-known/agent-card.json")
    print(f"[Degrading Analysis Worker/LangGraph] MAST failure injection ACTIVE")
    uvicorn.run(app.build(), host=HOST, port=PORT, log_level="warning")