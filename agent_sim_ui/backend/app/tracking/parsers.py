"""Per-simulator log parsers (SIM-UI-103).

Each parser classifies a single captured log line into zero or more
:class:`Transition`s. Parsing is regex/string-based against the *existing* log
formats (ChatDev/MetaGPT formats must not change — AGENTS.md convention) and is
strictly best-effort: an unknown or malformed line yields no transitions and
never raises.

A ``Transition.agent_id`` of ``None`` means "attribute to the instance's
currently-running agent" (resolved by the tracker).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..models import AgentState

# Leading log prefix such as "[2025-06-28 15:00:00 INFO] "
_PREFIX_RE = re.compile(r"^\[[^\]]*\]\s*")
_FM_RE = re.compile(r"\[FM-\d+\.\d+\]")
_ERROR_KEYWORDS = ("is dead", "halted", "terminal", "fatal error", "collapsed")


@dataclass
class Transition:
    """A requested state change for one agent (or the current agent if None)."""

    agent_id: Optional[str]
    to_state: AgentState
    failure_modes: List[str] = field(default_factory=list)


def _strip_prefix(line: str) -> str:
    return _PREFIX_RE.sub("", line, count=1)


class SimulatorStateParser:
    """Base parser. Subclasses override :meth:`_detect` for start/completion."""

    #: Sequential pipelines auto-complete the previous agent when a new one
    #: starts running. Concurrent topologies (swarm) set this False.
    sequential: bool = True

    def __init__(self) -> None:
        pass

    def classify(self, line: str, name_index: "NameIndex") -> List[Transition]:
        try:
            return self._classify(line, name_index)
        except Exception:  # noqa: BLE001 - parser must never crash the tracker
            return []

    def _classify(self, line: str, name_index: "NameIndex") -> List[Transition]:
        # 1) Error signals are checked on the *raw* line (FM tags are bracketed).
        fms = _FM_RE.findall(line)
        if fms:
            fm_codes = [f.strip("[]") for f in fms]
            return [Transition(name_index.find(line), AgentState.ERRORED, fm_codes)]

        low = line.lower()
        if any(k in low for k in _ERROR_KEYWORDS):
            return [Transition(name_index.find(line), AgentState.ERRORED, [])]

        if line.lstrip().startswith("Traceback (most recent call last)"):
            return [Transition(None, AgentState.ERRORED, [])]

        # 2) Start / completion detection on the prefix-stripped line.
        stripped = _strip_prefix(line)
        return self._detect(stripped, stripped.lower(), name_index)

    def _detect(self, line: str, low: str, name_index: "NameIndex") -> List[Transition]:
        return []


# ---------------------------------------------------------------------------
# Name index: maps text mentions -> agent_id
# ---------------------------------------------------------------------------
class NameIndex:
    """Resolve agent mentions in a line to an agent_id (longest match first)."""

    def __init__(self, pairs: List[tuple]):
        # pairs: list of (key_lower, agent_id); sorted by key length desc
        self._pairs = sorted(pairs, key=lambda p: len(p[0]), reverse=True)

    @classmethod
    def from_agents(cls, agents) -> "NameIndex":
        pairs: List[tuple] = []
        for a in agents:
            keys = {a.agent_name.lower(), a.agent_id.lower(), a.agent_id.replace("_", " ").lower()}
            for k in keys:
                if k:
                    pairs.append((k, a.agent_id))
        return cls(pairs)

    def find(self, text: str) -> Optional[str]:
        low = text.lower()
        for key, agent_id in self._pairs:
            if key in low:
                return agent_id
        return None

    def prefix_agent(self, line: str) -> Optional[str]:
        """If the line is of the form '<Agent>: ...', return its agent_id."""
        head = line.split(":", 1)[0].strip().lower()
        for key, agent_id in self._pairs:
            if key == head:
                return agent_id
        return None


# ---------------------------------------------------------------------------
# ChatDev
# ---------------------------------------------------------------------------
class ChatDevParser(SimulatorStateParser):
    sequential = True

    _SEMINAR_DONE = "[seminar conclusion]"

    def _detect(self, line: str, low: str, name_index: NameIndex) -> List[Transition]:
        # Completion of the current speaker
        if self._SEMINAR_DONE in low:
            return [Transition(None, AgentState.COMPLETED)]
        # An utterance line begins with "<Role>:" (after the timestamp prefix).
        agent_id = name_index.prefix_agent(line)
        if agent_id is not None:
            return [Transition(agent_id, AgentState.RUNNING)]
        return []


# ---------------------------------------------------------------------------
# MetaGPT
# ---------------------------------------------------------------------------
class MetaGPTParser(SimulatorStateParser):
    sequential = True

    _ACTION_RE = re.compile(r"\*\*\[action:.*?\]\*\*\s*[—\-:]?\s*(.+)$", re.IGNORECASE)
    _PUBLISHED_RE = re.compile(r"(.+?)\s+published\s+\w+", re.IGNORECASE)

    def _detect(self, line: str, low: str, name_index: NameIndex) -> List[Transition]:
        # Completion: "<Role> published <Action>"
        m = self._PUBLISHED_RE.search(line)
        if m:
            agent_id = name_index.find(m.group(1))
            if agent_id:
                return [Transition(agent_id, AgentState.COMPLETED)]
        # Start: "**[Action: X]** — <Role>"
        m = self._ACTION_RE.search(line)
        if m:
            agent_id = name_index.find(m.group(1))
            if agent_id:
                return [Transition(agent_id, AgentState.RUNNING)]
        return []


# ---------------------------------------------------------------------------
# Manual (swarm / orchestrator) — concurrent A2A
# ---------------------------------------------------------------------------
class ManualParser(SimulatorStateParser):
    sequential = False

    _START_HINTS = ("received", "handling", "request received", "invoking", "processing")
    _DONE_HINTS = ("responded", "completed", "finished", "done", "sent response")
    _ORCHESTRATOR_START_RE = re.compile(r"===\s*HUB\s*->\s*(\w+)\s+WORKER\s*===", re.IGNORECASE)
    _ORCHESTRATOR_DONE_RE = re.compile(r"===\s*FINAL\s+BRIEFING\s*\(hub\s+collected\s+\w+\s+artifact\)\s*===", re.IGNORECASE)
    _SWARM_HANDOFF_RE = re.compile(r"===\s*HANDOFF\s+\d+:\s*(.+?)\s*->\s*(.+?)\s*===", re.IGNORECASE)
    _SWARM_FINAL_RE = re.compile(r"===\s*FINAL\s+BRIEFING\s*\(writer'?s\s+artifact\)\s*===", re.IGNORECASE)

    _ROLE_ALIASES = {
        "research": "researcher",
        "analysis": "analyst",
        "writing": "writer",
    }

    def _normalize_role(self, raw: str) -> str:
        role = raw.strip().lower()
        role = re.sub(r"\s+output$", "", role)
        role = re.sub(r"\s+worker$", "", role)
        return self._ROLE_ALIASES.get(role, role)

    def _resolve_agent(self, raw: str, name_index: NameIndex) -> Optional[str]:
        role = self._normalize_role(raw)
        agent_id = name_index.find(role)
        return agent_id

    def _detect(self, line: str, low: str, name_index: NameIndex) -> List[Transition]:
        # Swarm handoff patterns
        m = self._SWARM_HANDOFF_RE.search(line)
        if m:
            source_raw, target_raw = m.group(1), m.group(2)
            transitions: List[Transition] = []
            source = self._resolve_agent(source_raw, name_index)
            target = self._resolve_agent(target_raw, name_index)
            if source and source != "client":
                transitions.append(Transition(source, AgentState.COMPLETED))
            if target:
                transitions.append(Transition(target, AgentState.RUNNING))
            if transitions:
                return transitions

        if self._SWARM_FINAL_RE.search(line):
            transitions = []
            for _, agent_id in name_index._pairs:
                transitions.append(Transition(agent_id, AgentState.COMPLETED))
            return transitions

        # Check for orchestrator-specific patterns first
        m = self._ORCHESTRATOR_START_RE.search(line)
        if m:
            role = m.group(1)
            agent_id = self._resolve_agent(role, name_index)
            if agent_id:
                return [Transition(agent_id, AgentState.RUNNING)]

        # Check for orchestrator completion
        if self._ORCHESTRATOR_DONE_RE.search(line):
            # Mark all orchestrator agents as completed
            transitions = []
            for _, agent_id in name_index._pairs:
                transitions.append(Transition(agent_id, AgentState.COMPLETED))
            return transitions

        # Fall back to generic hints
        agent_id = name_index.find(line)
        if agent_id is None:
            return []
        if any(h in low for h in self._DONE_HINTS):
            return [Transition(agent_id, AgentState.COMPLETED)]
        if any(h in low for h in self._START_HINTS):
            return [Transition(agent_id, AgentState.RUNNING)]
        return []


# ---------------------------------------------------------------------------
# HyperAgent — planner + specialists (sequential-ish)
# ---------------------------------------------------------------------------
class HyperAgentParser(SimulatorStateParser):
    sequential = True

    _START_HINTS = ("action", "executing", "started", "processing", "dispatch")
    _DONE_HINTS = ("completed", "finished", "done", "result", "final_status")

    def _detect(self, line: str, low: str, name_index: NameIndex) -> List[Transition]:
        agent_id = name_index.find(line)
        if agent_id is None:
            return []
        if any(h in low for h in self._DONE_HINTS):
            return [Transition(agent_id, AgentState.COMPLETED)]
        if any(h in low for h in self._START_HINTS):
            return [Transition(agent_id, AgentState.RUNNING)]
        return []


class GenericParser(SimulatorStateParser):
    """Fallback parser: handles only the common error signals."""

    sequential = True


PARSERS: Dict[str, SimulatorStateParser] = {
    "chatdev": ChatDevParser(),
    "metagpt": MetaGPTParser(),
    "manual-swarm": ManualParser(),
    "manual-orchestrator": ManualParser(),
    "hyperagent": HyperAgentParser(),
}


def get_parser(simulator_id: str) -> SimulatorStateParser:
    return PARSERS.get(simulator_id, GenericParser())
