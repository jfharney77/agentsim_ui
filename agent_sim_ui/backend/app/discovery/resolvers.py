"""Per-simulator agent resolvers (SIM-UI-101).

Each resolver knows how to extract the ordered agent roster for one kind of
simulator using a *static* strategy (read JSON, parse a dict via ``ast``, list
directories) — never by importing simulator modules (which could trigger LLM
calls or side effects).

A resolver returns a list of :class:`AgentDescriptor`. If its primary source is
missing/unparseable it raises, and the registry falls back to a hard-coded
roster for the known simulator (SCENARIO-101-06).
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..models import AgentDescriptor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(name: str) -> str:
    """'Chief Executive Officer' -> 'chief_executive_officer'."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return slug.strip("_")


def humanize(name: str) -> str:
    """'researcher' -> 'Researcher'; leave already-spaced names untouched."""
    if " " in name or any(c.isupper() for c in name):
        return name
    return name.replace("_", " ").title()


def module_docstring(path: Path) -> Optional[str]:
    """Return the first line of a Python module's docstring, or None."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    doc = ast.get_docstring(tree)
    if not doc:
        return None
    return doc.strip().splitlines()[0].strip()


@dataclass
class ResolverContext:
    """Shared metadata injected into every AgentDescriptor a resolver builds."""

    simulator_id: str
    framework: str
    topology: str

    def build(
        self,
        *,
        order: int,
        agent_name: str,
        role: str,
        description: str = "",
        extra: Optional[Dict] = None,
    ) -> AgentDescriptor:
        metadata = {
            "simulator_id": self.simulator_id,
            "topology": self.topology,
            "framework": self.framework,
        }
        if extra:
            metadata.update(extra)
        return AgentDescriptor(
            agent_id=slugify(role),
            agent_name=agent_name,
            role=role,
            order=order,
            framework=self.framework,
            description=description or f"{agent_name} agent in the {self.simulator_id} simulator.",
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class AgentResolver:
    """Strategy interface: resolve a simulator path to an agent roster."""

    def resolve(self, simulator_path: Path, ctx: ResolverContext) -> List[AgentDescriptor]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# ChatDev — roles are the keys of config/RoleConfig.json, in file order.
# ---------------------------------------------------------------------------
class ChatDevResolver(AgentResolver):
    def resolve(self, simulator_path: Path, ctx: ResolverContext) -> List[AgentDescriptor]:
        config = simulator_path / "config" / "RoleConfig.json"
        data = json.loads(config.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data:
            raise ValueError(f"RoleConfig.json is empty or malformed: {config}")
        agents: List[AgentDescriptor] = []
        for order, (role, prompt_lines) in enumerate(data.items()):
            description = ""
            if isinstance(prompt_lines, list) and len(prompt_lines) >= 3:
                description = str(prompt_lines[2]).strip()[:200]
            agents.append(ctx.build(order=order, agent_name=role, role=role, description=description))
        return agents


# ---------------------------------------------------------------------------
# MetaGPT — roles are the keys of the ``agent_states`` dict in run_metagpt_sim.py
# ---------------------------------------------------------------------------
_METAGPT_DESCRIPTIONS = {
    "Product Manager": "Writes the Product Requirements Document (PRD).",
    "Architect": "Produces the system design from the PRD.",
    "Project Manager": "Breaks the system design into implementation tasks.",
    "Engineer": "Implements the code from tasks and design.",
    "QA Engineer": "Reviews the code against the PRD and writes tests.",
}


class MetaGPTResolver(AgentResolver):
    def resolve(self, simulator_path: Path, ctx: ResolverContext) -> List[AgentDescriptor]:
        source = simulator_path / "run_metagpt_sim.py"
        roles = self._parse_agent_states(source)
        if not roles:
            raise ValueError(f"Could not parse 'agent_states' roles from {source}")
        return [
            ctx.build(
                order=order,
                agent_name=role,
                role=role,
                description=_METAGPT_DESCRIPTIONS.get(role, ""),
            )
            for order, role in enumerate(roles)
        ]

    @staticmethod
    def _parse_agent_states(source: Path) -> List[str]:
        """Statically extract the string keys of the ``agent_states = {...}`` dict."""
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if "agent_states" in targets:
                    keys: List[str] = []
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            keys.append(key.value)
                    return keys
        return []


# ---------------------------------------------------------------------------
# Manual (swarm / orchestrator) — roles are subdirs of agentic_mesh/
# ---------------------------------------------------------------------------
class ManualResolver(AgentResolver):
    def resolve(self, simulator_path: Path, ctx: ResolverContext) -> List[AgentDescriptor]:
        mesh = simulator_path / "agentic_mesh"
        if not mesh.is_dir():
            raise ValueError(f"agentic_mesh directory not found: {mesh}")
        role_dirs = sorted(
            d
            for d in mesh.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        )
        if not role_dirs:
            raise ValueError(f"No role packages found under {mesh}")
        agents: List[AgentDescriptor] = []
        for order, role_dir in enumerate(role_dirs):
            role = role_dir.name
            description = self._role_description(role_dir, role)
            impls = [
                impl.name
                for impl in role_dir.iterdir()
                if impl.is_dir() and impl.name in ("a2a", "langgraph")
            ]
            agents.append(
                ctx.build(
                    order=order,
                    agent_name=humanize(role),
                    role=role,
                    description=description,
                    extra={"implementations": sorted(impls)},
                )
            )
        return agents

    @staticmethod
    def _role_description(role_dir: Path, role: str) -> str:
        for impl in ("langgraph", "a2a"):
            candidate = role_dir / impl / f"{role}.py"
            doc = module_docstring(candidate)
            if doc:
                return doc[:200]
        return ""


# ---------------------------------------------------------------------------
# HyperAgent — agents defined in agents/ ; role names per config/runner.
# ---------------------------------------------------------------------------
# role -> implementation file under agents/
_HYPERAGENT_AGENTS = [
    ("planner", "planner.py"),
    ("navigator", "navigator.py"),
    ("editor", "code_editor.py"),
    ("executor", "executor.py"),
]


class HyperAgentResolver(AgentResolver):
    def resolve(self, simulator_path: Path, ctx: ResolverContext) -> List[AgentDescriptor]:
        agents_dir = simulator_path / "agents"
        if not agents_dir.is_dir():
            raise ValueError(f"agents directory not found: {agents_dir}")
        agents: List[AgentDescriptor] = []
        for order, (role, filename) in enumerate(_HYPERAGENT_AGENTS):
            doc = module_docstring(agents_dir / filename) or ""
            agents.append(
                ctx.build(
                    order=order,
                    agent_name=humanize(role),
                    role=role,
                    description=doc[:200],
                )
            )
        return agents
