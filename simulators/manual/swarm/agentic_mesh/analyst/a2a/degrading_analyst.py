"""Degrading Analyst — A2A version.

Same Agent Card and skill as the normal analyst. From the perspective of
swarm.py or hub.py, this agent is indistinguishable at discovery time —
it advertises the same 'analysis' skill on the same port. The degradation
is entirely internal, which is exactly the blind spot described in the
README: "there's no single trace of the whole run."

Uses degrading_brain.degrading_think() instead of brain.think(), injecting
MAST taxonomy failure modes that worsen over successive calls.
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

from simulators.manual.swarm.degrading_brain import DegradationState, degrading_think
from simulators.manual.swarm.ports import host_port

HOST, PORT = host_port("analyst")

SKILL = AgentSkill(
    id="analysis",
    name="Strategic analysis",
    description=(
        "Turns raw research facts into strategic risks, opportunities, "
        "and a one-line fit assessment."
    ),
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


class DegradingExecutor(AgentExecutor):
    """A2A executor that degrades over successive calls.

    Each call advances the internal DegradationState, causing MAST
    failure modes to fire with increasing probability.
    """

    def __init__(self) -> None:
        self._state = DegradationState()

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        user_text = context.get_user_input()
        result = degrading_think(SYSTEM_PROMPT, user_text, self._state)

        # Export telemetry data after each call
        telemetry_data = {
            "call": self._state.call_count,
            "level": self._state.degradation_level,
            "active": len(self._state.active_failures),
            "severity": self._state.total_severity,
            "cumulative": self._state.cumulative_severity,
            "critical_cycles": self._state.cycles_in_critical,
            "failures": self._state.active_failures.copy()
        }
        
        # Append to telemetry file
        with open("degradation_telemetry.json", "a") as f:
            f.write(json.dumps(telemetry_data) + "\n")

        # Log terminal state for monitoring systems
        if self._state.is_terminal:
            print(f"  [DEGRADING ANALYST] ☠ Agent has reached terminal state")
            print(f"  [DEGRADING ANALYST] Reason: {self._state.terminal_reason}")
            print(f"  [DEGRADING ANALYST] Total calls before death: {self._state.call_count}")

        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError("cancellation not supported")


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}/"
    card = AgentCard(
        name="Degrading Analyst",
        description=(
            "An analyst agent that progressively degrades, "
            "simulating MAST taxonomy failure modes."
        ),
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[SKILL],
    )
    handler = DefaultRequestHandler(
        agent_executor=DegradingExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(agent_card=card, http_handler=handler)
    print(f"[Degrading Analyst/A2A] listening on {url}")
    print(f"[Degrading Analyst/A2A] card at {url}.well-known/agent-card.json")
    print(f"[Degrading Analyst/A2A] MAST failure injection ACTIVE")
    uvicorn.run(app.build(), host=HOST, port=PORT, log_level="warning")