"""SimulatorRegistry — discovery of simulators and their agents (SIM-UI-101).

Scans the parent repo's ``simulators/`` directory, resolves the correct agent
roster for each of the five known simulators using per-simulator
:class:`AgentResolver` strategies, and exposes them as :class:`Simulator`
objects (SIM-UI-100 Section 8.1).

Resilience (SIM-UI-101 acceptance criteria):
  * A simulator whose directory is missing is skipped with a logged warning.
  * A known simulator whose source can't be parsed falls back to a hard-coded
    roster (SCENARIO-101-06) rather than crashing the service.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..config import Settings, get_settings
from ..models import (
    AgentDescriptor,
    LaunchKind,
    LaunchSpec,
    Simulator,
    WorkflowDescriptor,
)
from .resolvers import (
    AgentResolver,
    ChatDevResolver,
    HyperAgentResolver,
    ManualResolver,
    MetaGPTResolver,
    ResolverContext,
)

logger = logging.getLogger(__name__)


@dataclass
class SimulatorDefinition:
    """Static definition of one known simulator."""

    id: str
    name: str
    rel_path: str          # relative to simulators/
    topology: str
    framework: str
    resolver: AgentResolver
    fallback_roles: List[str]
    launch_factory: "callable"  # (repo_root, sim_path) -> LaunchSpec
    # Built-in named agent subsets; overridden by a workflows.json in the
    # simulator directory. agent_ids referencing agents missing from the
    # resolved roster are dropped at build time.
    default_workflows: List[WorkflowDescriptor] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Launch spec factories (consumed later by SIM-UI-102)
# ---------------------------------------------------------------------------
_PROVIDER_ENV = ["LLM_PROVIDER"]


def _python_launch(entrypoint: str):
    def factory(repo_root: Path, sim_path: Path) -> LaunchSpec:
        return LaunchSpec(
            kind=LaunchKind.PYTHON,
            command="python",
            args=[entrypoint],
            cwd=str(sim_path),
            env_required=_PROVIDER_ENV,
            requires_start_script=False,
        )

    return factory


def _bash_launch(start_script: str, run_script: str):
    def factory(repo_root: Path, sim_path: Path) -> LaunchSpec:
        return LaunchSpec(
            kind=LaunchKind.BASH,
            command="bash",
            args=[run_script],
            cwd=str(repo_root),
            env_required=_PROVIDER_ENV,
            requires_start_script=True,
            start_command=start_script,
            # start_swarm.sh / start_orchestrator.sh print "... agents up ..."
            ready_marker="up",
            ready_timeout_seconds=90,
            # Per-instance port isolation (SIM-UI-102 SCENARIO-102-04). Scripts
            # must honor PORT_BASE; a thin wrapper lives under agent_sim_ui.
            port_base_env="PORT_BASE",
            port_base=9001,
            port_stride=10,
        )

    return factory


def _hyperagent_launch():
    def factory(repo_root: Path, sim_path: Path) -> LaunchSpec:
        # Thin runner module under agent_sim_ui that invokes
        # SimulationRunner(...).run(task). Invoked by file path so it does not
        # require agent_sim_ui to be an installed package.
        runner = (
            Path(__file__).resolve().parents[1] / "runners" / "hyperagent_runner.py"
        )
        return LaunchSpec(
            kind=LaunchKind.PYTHON,
            command="python",
            args=[str(runner)],
            cwd=str(repo_root),
            env_required=_PROVIDER_ENV,
            requires_start_script=False,
        )

    return factory


# ---------------------------------------------------------------------------
# The five known simulators
# ---------------------------------------------------------------------------
_DEFINITIONS: List[SimulatorDefinition] = [
    SimulatorDefinition(
        id="chatdev",
        name="ChatDev",
        rel_path="chatdev",
        topology="phase-based pipeline",
        framework="Direct LLM (ChatDev)",
        resolver=ChatDevResolver(),
        fallback_roles=[
            "Chief Executive Officer",
            "Chief Product Officer",
            "Chief Technology Officer",
            "Programmer",
            "Code Reviewer",
            "Software Test Engineer",
        ],
        launch_factory=_python_launch("run_chatdev_sim.py"),
        default_workflows=[
            WorkflowDescriptor(
                id="build_and_test",
                name="Build & test",
                description="Implementation loop: code, review, verify.",
                agent_ids=["programmer", "code_reviewer", "software_test_engineer"],
            ),
            WorkflowDescriptor(
                id="leadership_review",
                name="Leadership review",
                description="Executive alignment on product and architecture.",
                agent_ids=[
                    "chief_executive_officer",
                    "chief_product_officer",
                    "chief_technology_officer",
                ],
            ),
        ],
    ),
    SimulatorDefinition(
        id="metagpt",
        name="MetaGPT",
        rel_path="metagpt",
        topology="pub/sub message pool",
        framework="Direct LLM (MetaGPT)",
        resolver=MetaGPTResolver(),
        fallback_roles=[
            "Product Manager",
            "Architect",
            "Project Manager",
            "Engineer",
            "QA Engineer",
        ],
        launch_factory=_python_launch("run_metagpt_sim.py"),
        default_workflows=[
            WorkflowDescriptor(
                id="planning",
                name="Planning",
                description="PRD → system design → task breakdown.",
                agent_ids=["product_manager", "architect", "project_manager"],
            ),
            WorkflowDescriptor(
                id="delivery",
                name="Delivery",
                description="Implementation and QA only.",
                agent_ids=["engineer", "qa_engineer"],
            ),
        ],
    ),
    SimulatorDefinition(
        id="manual-swarm",
        name="Manual — Swarm",
        rel_path="manual/swarm",
        topology="peer-to-peer (A2A)",
        framework="A2A / LangGraph",
        resolver=ManualResolver(),
        fallback_roles=["researcher", "analyst", "writer"],
        launch_factory=_bash_launch(
            "scripts/manual/start_swarm.sh", "scripts/manual/run_swarm.sh"
        ),
        default_workflows=[
            WorkflowDescriptor(
                id="research_pipeline",
                name="Research pipeline",
                description="Researcher → Analyst → Writer.",
                agent_ids=["researcher", "analyst", "writer"],
            ),
        ],
    ),
    SimulatorDefinition(
        id="manual-orchestrator",
        name="Manual — Orchestrator",
        rel_path="manual/orchestrator",
        topology="hub-and-spoke (A2A)",
        framework="A2A / LangGraph",
        resolver=ManualResolver(),
        fallback_roles=["researcher", "analyst", "writer"],
        launch_factory=_bash_launch(
            "scripts/manual/start_orchestrator.sh", "scripts/manual/run_orchestrator.sh"
        ),
        default_workflows=[
            WorkflowDescriptor(
                id="research_pipeline",
                name="Research pipeline",
                description="Researcher → Analyst → Writer.",
                agent_ids=["researcher", "analyst", "writer"],
            ),
        ],
    ),
    SimulatorDefinition(
        id="hyperagent",
        name="HyperAgent",
        rel_path="hyperagent",
        topology="planner + specialists",
        framework="Direct LLM (HyperAgent)",
        resolver=HyperAgentResolver(),
        fallback_roles=["planner", "navigator", "editor", "executor"],
        launch_factory=_hyperagent_launch(),
        default_workflows=[
            WorkflowDescriptor(
                id="code_change",
                name="Code change",
                description="Navigate the repo, edit, and execute — no planner.",
                agent_ids=["navigator", "editor", "executor"],
            ),
        ],
    ),
]


class SimulatorRegistryInterface:
    """Storage-agnostic interface (SIM-UI-101 Data Model)."""

    def list_all(self) -> List[Simulator]:
        raise NotImplementedError

    def get(self, simulator_id: str) -> Optional[Simulator]:
        raise NotImplementedError

    def get_agents(self, simulator_id: str) -> List[AgentDescriptor]:
        raise NotImplementedError

    def reload(self) -> None:
        raise NotImplementedError


class SimulatorRegistry(SimulatorRegistryInterface):
    """Filesystem-backed registry of the known simulators."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._cache: Optional[Dict[str, Simulator]] = None

    # -- public API --------------------------------------------------------
    def list_all(self) -> List[Simulator]:
        return list(self._ensure_cache().values())

    def get(self, simulator_id: str) -> Optional[Simulator]:
        return self._ensure_cache().get(simulator_id)

    def get_agents(self, simulator_id: str) -> List[AgentDescriptor]:
        sim = self.get(simulator_id)
        return list(sim.agents) if sim else []

    def reload(self) -> None:
        self._cache = None
        self._ensure_cache()

    # -- internals ---------------------------------------------------------
    def _ensure_cache(self) -> Dict[str, Simulator]:
        if self._cache is None:
            self._cache = self._build()
        return self._cache

    def _build(self) -> Dict[str, Simulator]:
        simulators_dir = self._settings.simulators_dir
        repo_root = self._settings.repo_root
        result: Dict[str, Simulator] = {}

        for defn in _DEFINITIONS:
            sim_path = simulators_dir / defn.rel_path
            if not sim_path.is_dir():
                logger.warning(
                    "Skipping simulator '%s': path not found (%s)", defn.id, sim_path
                )
                continue

            ctx = ResolverContext(
                simulator_id=defn.id,
                framework=defn.framework,
                topology=defn.topology,
            )

            agents = self._resolve_agents(defn, sim_path, ctx)
            launch = defn.launch_factory(repo_root, sim_path)

            result[defn.id] = Simulator(
                id=defn.id,
                name=defn.name,
                path=str(sim_path),
                topology=defn.topology,
                launch=launch,
                agents=agents,
                workflows=self._resolve_workflows(defn, sim_path, agents),
            )

        return result

    @staticmethod
    def _resolve_workflows(
        defn: SimulatorDefinition, sim_path: Path, agents: List[AgentDescriptor]
    ) -> List[WorkflowDescriptor]:
        """Predefined workflows for a simulator (SIM-UI-101).

        A ``workflows.json`` in the simulator directory overrides the built-in
        defaults, so meshes can define their runnable sub-graphs ahead of time:

            [{"id": "research_pipeline", "name": "Research pipeline",
              "description": "...", "agent_ids": ["researcher", "analyst"]}]

        agent_ids not present in the resolved roster are dropped; a workflow
        left with no agents (or an unparseable file) is skipped with a warning
        rather than crashing discovery.
        """
        candidates: List[WorkflowDescriptor] = list(defn.default_workflows)
        wf_file = sim_path / "workflows.json"
        if wf_file.is_file():
            try:
                raw = json.loads(wf_file.read_text(encoding="utf-8"))
                candidates = [WorkflowDescriptor(**item) for item in raw]
            except Exception as exc:  # noqa: BLE001 - resilience per SIM-UI-101
                logger.warning(
                    "Ignoring malformed workflows.json for '%s' (%s); "
                    "using built-in workflows.",
                    defn.id,
                    exc,
                )

        roster_ids = {a.agent_id for a in agents}
        workflows: List[WorkflowDescriptor] = []
        for wf in candidates:
            known = [aid for aid in wf.agent_ids if aid in roster_ids]
            if dropped := set(wf.agent_ids) - roster_ids:
                logger.warning(
                    "Workflow '%s' of '%s' references unknown agents %s; dropping them.",
                    wf.id,
                    defn.id,
                    sorted(dropped),
                )
            if not known:
                continue
            workflows.append(wf.model_copy(update={"agent_ids": known}))
        return workflows

    @staticmethod
    def _resolve_agents(
        defn: SimulatorDefinition, sim_path: Path, ctx: ResolverContext
    ) -> List[AgentDescriptor]:
        try:
            agents = defn.resolver.resolve(sim_path, ctx)
            if agents:
                return agents
            raise ValueError("resolver returned no agents")
        except Exception as exc:  # noqa: BLE001 - resilience is required by spec
            logger.warning(
                "Agent resolution failed for '%s' (%s); using fallback roster.",
                defn.id,
                exc,
            )
            return [
                ctx.build(order=order, agent_name=_humanize(role), role=role)
                for order, role in enumerate(defn.fallback_roles)
            ]


def _humanize(name: str) -> str:
    if " " in name or any(c.isupper() for c in name):
        return name
    return name.replace("_", " ").title()
