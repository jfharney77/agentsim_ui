"""Tests for SIM-UI-103 Agent State Tracking & Event Streaming.

Covers SCENARIO-103-01 .. SCENARIO-103-08. Canned log fragments mimic the real
ChatDev / MetaGPT log formats (including the "[timestamp LEVEL] " prefix).
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.config import Settings
from app.discovery.registry import SimulatorRegistry
from app.models import AgentRuntimeState, AgentState, InstanceDescriptor
from app.tracking import StateTracker


REGISTRY = SimulatorRegistry(settings=Settings())


def make_descriptor(sim_id: str, instance_id="i1", group="g1") -> InstanceDescriptor:
    agents = [
        AgentRuntimeState(agent_id=a.agent_id, agent_name=a.agent_name)
        for a in REGISTRY.get_agents(sim_id)
    ]
    return InstanceDescriptor(
        instance_id=instance_id, run_group_id=group,
        simulator_id=sim_id, index=0, agents=agents,
    )


def _state(tracker, instance_id, agent_id):
    return next(s for s in tracker.snapshot(instance_id) if s.agent_id == agent_id)


# --- SCENARIO-103-01 -------------------------------------------------------
def test_all_agents_start_not_started():
    tracker = StateTracker()
    desc = make_descriptor("chatdev")
    tracker.register_instance(desc)
    snap = tracker.snapshot("i1")
    assert len(snap) == 6
    assert all(s.state == AgentState.NOT_STARTED for s in snap)


# --- SCENARIO-103-02 -------------------------------------------------------
def test_chatdev_agent_transitions_to_running():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("chatdev"))
    line = "[2025-06-28 15:00:00 INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**"
    tracker.process_line("i1", line)
    assert _state(tracker, "i1", "programmer").state == AgentState.RUNNING
    events = tracker.get_events("i1")
    assert any(e.agent_id == "programmer" and e.new_state == AgentState.RUNNING for e in events)


# --- SCENARIO-103-03 -------------------------------------------------------
def test_metagpt_completion_detected():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("metagpt"))
    tracker.process_line("i1", "[2025-06-28 15:00:00 INFO] Engineer published WriteCode:")
    assert _state(tracker, "i1", "engineer").state == AgentState.COMPLETED


# --- SCENARIO-103-04 -------------------------------------------------------
def test_failure_mode_marks_errored():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("metagpt"))
    tracker.process_line("i1", "[2025-06-28 15:00:00 INFO] **[Action: WriteDesign]** — Architect")
    assert _state(tracker, "i1", "architect").state == AgentState.RUNNING
    tracker.process_line("i1", "[2025-06-28 15:00:01 INFO] Architect: [FM-2.4] Information withholding detected")
    arch = _state(tracker, "i1", "architect")
    assert arch.state == AgentState.ERRORED
    assert "FM-2.4" in arch.failure_modes


# --- SCENARIO-103-05 -------------------------------------------------------
def test_terminal_halt_marks_errored():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("metagpt"))
    tracker.process_line("i1", "[2025-06-28 15:00:00 INFO] Pipeline halted: Product Manager is dead. Reason: terminal")
    assert _state(tracker, "i1", "product_manager").state == AgentState.ERRORED


# --- SCENARIO-103-06 -------------------------------------------------------
def test_process_exit_finalization_success():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("chatdev", instance_id="ok"))
    tracker.process_line("ok", "[2025-06-28 15:00:00 INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**")
    assert _state(tracker, "ok", "programmer").state == AgentState.RUNNING
    tracker.on_process_exit("ok", 0)
    assert _state(tracker, "ok", "programmer").state == AgentState.COMPLETED
    # untouched agents stay not_started
    assert _state(tracker, "ok", "code_reviewer").state == AgentState.NOT_STARTED


def test_process_exit_finalization_failure():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("chatdev", instance_id="bad"))
    tracker.process_line("bad", "[2025-06-28 15:00:00 INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**")
    tracker.on_process_exit("bad", 1)
    assert _state(tracker, "bad", "programmer").state == AgentState.ERRORED


# --- SCENARIO-103-07 -------------------------------------------------------
def test_snapshot_matches_cumulative_events():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("metagpt"))
    lines = [
        "[INFO] **[Action: WritePRD]** — Product Manager",
        "[INFO] Product Manager published WritePRD:",
        "[INFO] **[Action: WriteDesign]** — Architect",
        "[INFO] Architect: [FM-2.4] withholding",
        "[INFO] **[Action: WriteCode]** — Engineer",
        "[INFO] Engineer published WriteCode:",
    ]
    for ln in lines:
        tracker.process_line("i1", ln)

    # Reconstruct final states purely from the emitted events.
    reconstructed = {}
    for e in tracker.get_events("i1"):
        reconstructed[e.agent_id] = e.new_state
    snap = {s.agent_id: s.state for s in tracker.snapshot("i1")}
    for agent_id, state in reconstructed.items():
        assert snap[agent_id] == state


# --- SCENARIO-103-08 -------------------------------------------------------
def test_stream_push_within_latency_budget():
    async def run():
        tracker = StateTracker()
        tracker.register_instance(make_descriptor("chatdev"))
        stream = tracker.subscribe("g1")
        # Prime the subscription, then trigger a transition.
        async def emit():
            await asyncio.sleep(0.01)
            tracker.process_line("i1", "[INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**")

        asyncio.create_task(emit())
        start = time.monotonic()
        event = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
        elapsed = time.monotonic() - start
        assert event.agent_id == "programmer"
        assert event.new_state == AgentState.RUNNING
        assert elapsed < 1.0

    asyncio.run(run())


def test_unknown_line_never_crashes():
    tracker = StateTracker()
    tracker.register_instance(make_descriptor("chatdev"))
    # garbage / unrelated lines should be no-ops
    for ln in ["", "random noise", "12345", "System: **[chatting]**"]:
        tracker.process_line("i1", ln)
    assert all(s.state == AgentState.NOT_STARTED for s in tracker.snapshot("i1"))


# --- Agent scope: out-of-scope agents never transition ---------------------
def test_out_of_scope_agent_never_transitions():
    tracker = StateTracker()
    desc = make_descriptor("chatdev")
    # Mark the Programmer out of scope; its running log line must be ignored.
    for s in desc.agents:
        if s.agent_id == "programmer":
            s.in_scope = False
    tracker.register_instance(desc)

    line = "[2025-06-28 15:00:00 INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**"
    tracker.process_line("i1", line)

    assert _state(tracker, "i1", "programmer").state == AgentState.NOT_STARTED
    assert not any(e.agent_id == "programmer" for e in tracker.get_events("i1"))
