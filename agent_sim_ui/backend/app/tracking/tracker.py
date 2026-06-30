"""StateTracker — live agent state derivation & event streaming (SIM-UI-103).

The tracker is a :class:`LaunchSink`: it consumes the captured output and
lifecycle events from the launcher (SIM-UI-102), derives each agent's state via
a per-simulator parser (SIM-UI-103 :mod:`parsers`), and exposes both:

  * a **poll snapshot** (`snapshot`) — always available, and
  * a **push stream** (`subscribe`) — an async iterator of `StateChangeEvent`s.

State is kept per ``(instance_id, agent_id)`` and mutates the same
``AgentRuntimeState`` objects held by the instance descriptor, so a launcher
snapshot and the tracker stay consistent.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, List, Optional, Set

from ..launcher.sinks import LaunchSink
from ..models import (
    AgentRuntimeState,
    AgentState,
    InstanceDescriptor,
    InstanceStatus,
    StateChangeEvent,
)
from .parsers import NameIndex, SimulatorStateParser, get_parser

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _InstanceTrack:
    instance_id: str
    run_group_id: str
    simulator_id: str
    parser: SimulatorStateParser
    agents: Dict[str, AgentRuntimeState]
    name_index: NameIndex
    current_running: Optional[str] = None
    had_error: bool = False
    events: List[StateChangeEvent] = field(default_factory=list)


class StateTrackerInterface:
    def on_log_line(self, instance_id: str, line: str) -> None:
        raise NotImplementedError

    def on_process_exit(self, instance_id: str, return_code: int) -> None:
        raise NotImplementedError

    def snapshot(self, instance_id: str) -> List[AgentRuntimeState]:
        raise NotImplementedError

    def subscribe(self, run_group_id: str) -> AsyncIterator[StateChangeEvent]:
        raise NotImplementedError


class StateTracker(StateTrackerInterface, LaunchSink):
    def __init__(self) -> None:
        self._instances: Dict[str, _InstanceTrack] = {}
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._listeners: List = []  # synchronous callables(StateChangeEvent)

    def add_listener(self, listener) -> None:
        """Register a synchronous callback invoked on every emitted event.

        Used by the run store (SIM-UI-104) to persist each transition.
        """
        self._listeners.append(listener)

    # -- registration ------------------------------------------------------
    def register_instance(self, descriptor: InstanceDescriptor) -> None:
        agents = {a.agent_id: a for a in descriptor.agents}
        track = _InstanceTrack(
            instance_id=descriptor.instance_id,
            run_group_id=descriptor.run_group_id,
            simulator_id=descriptor.simulator_id,
            parser=get_parser(descriptor.simulator_id),
            agents=agents,
            name_index=NameIndex.from_agents(descriptor.agents),
        )
        self._instances[descriptor.instance_id] = track

    # -- LaunchSink hooks ---------------------------------------------------
    async def on_instance_created(self, instance: InstanceDescriptor) -> None:
        self.register_instance(instance)

    async def on_log_line(self, instance_id: str, line: str) -> None:  # type: ignore[override]
        self.process_line(instance_id, line)

    async def on_instance_exit(
        self, instance_id: str, return_code: int, status: InstanceStatus
    ) -> None:
        self.on_process_exit(instance_id, return_code)

    # -- core logic --------------------------------------------------------
    def process_line(self, instance_id: str, line: str) -> None:
        track = self._instances.get(instance_id)
        if track is None:
            return
        transitions = track.parser.classify(line, track.name_index)
        for t in transitions:
            if t.to_state == AgentState.ERRORED:
                track.had_error = True
            agent_id = t.agent_id or track.current_running
            if agent_id is None:
                continue
            self._apply(track, agent_id, t.to_state, t.failure_modes, line)

    def on_process_exit(self, instance_id: str, return_code: int) -> None:
        track = self._instances.get(instance_id)
        if track is None:
            return
        errored = (return_code != 0) or track.had_error
        final = AgentState.ERRORED if errored else AgentState.COMPLETED
        for st in track.agents.values():
            if st.state == AgentState.RUNNING:
                self._set(track, st, final, [], f"process exit rc={return_code}")
        track.current_running = None

    def snapshot(self, instance_id: str) -> List[AgentRuntimeState]:
        track = self._instances.get(instance_id)
        if track is None:
            return []
        return list(track.agents.values())

    def get_events(self, instance_id: str) -> List[StateChangeEvent]:
        track = self._instances.get(instance_id)
        return list(track.events) if track else []

    async def subscribe(self, run_group_id: str) -> AsyncIterator[StateChangeEvent]:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_group_id].add(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._subscribers[run_group_id].discard(queue)

    # -- internals ---------------------------------------------------------
    def _apply(
        self,
        track: _InstanceTrack,
        agent_id: str,
        to_state: AgentState,
        fms: List[str],
        line: str,
    ) -> None:
        st = track.agents.get(agent_id)
        if st is None:
            return

        # Sequential pipelines: starting a new agent completes the previous one.
        if (
            to_state == AgentState.RUNNING
            and track.parser.sequential
            and track.current_running
            and track.current_running != agent_id
        ):
            prev = track.agents.get(track.current_running)
            if prev is not None and prev.state == AgentState.RUNNING:
                self._set(track, prev, AgentState.COMPLETED, [], line)

        self._set(track, st, to_state, fms, line)

        if to_state == AgentState.RUNNING:
            track.current_running = agent_id
        elif track.current_running == agent_id and to_state in (
            AgentState.COMPLETED,
            AgentState.ERRORED,
        ):
            track.current_running = None

    def _set(
        self,
        track: _InstanceTrack,
        st: AgentRuntimeState,
        to_state: AgentState,
        fms: List[str],
        line: str,
    ) -> None:
        new_fms = [fm for fm in fms if fm not in st.failure_modes]
        if st.state == to_state and not new_fms:
            return  # no-op

        old = st.state
        st.state = to_state
        now = _now()
        if to_state == AgentState.RUNNING and st.started_at is None:
            st.started_at = now
        if to_state in (AgentState.COMPLETED, AgentState.ERRORED):
            st.ended_at = now
        for fm in new_fms:
            st.failure_modes.append(fm)
        st.last_event = line[:300]

        self._emit(track, st, old, to_state, new_fms)

    def _emit(
        self,
        track: _InstanceTrack,
        st: AgentRuntimeState,
        old: AgentState,
        new: AgentState,
        fms: List[str],
    ) -> None:
        event = StateChangeEvent(
            instance_id=track.instance_id,
            run_group_id=track.run_group_id,
            agent_id=st.agent_id,
            agent_name=st.agent_name,
            old_state=old,
            new_state=new,
            ts=_now(),
            failure_modes=list(st.failure_modes),
        )
        track.events.append(event)
        for queue in list(self._subscribers.get(track.run_group_id, ())):
            try:
                queue.put_nowait(event)
            except Exception:  # noqa: BLE001
                pass
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:  # noqa: BLE001
                logger.exception("state event listener failed")
