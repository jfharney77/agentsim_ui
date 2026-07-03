"""Shared data model for the Agent Sim UI (SIM-UI-100, Section 8).

These pydantic models are the contract shared by every other spec: discovery
(101), launcher (102), state tracking (103), logging (104), and the API (105).
Keeping them here means the four-state color model and simulator/agent shapes
have a single source of truth.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums (SIM-UI-100 Sections 8.2 / 8.4)
# ---------------------------------------------------------------------------
class AgentState(str, Enum):
    """The four visual states of an agent circle (SIM-UI-100 Section 8.2)."""

    NOT_STARTED = "not_started"  # white  — agent has not been run yet
    RUNNING = "running"          # yellow — agent is currently executing
    COMPLETED = "completed"      # light green — finished successfully
    ERRORED = "errored"          # light red — committed an error / failure mode


class InstanceStatus(str, Enum):
    """Lifecycle status of a single simulator instance (SIM-UI-100 Section 8.4)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LaunchKind(str, Enum):
    """How a simulator is started (consumed by SIM-UI-102)."""

    PYTHON = "python"
    BASH = "bash"


# ---------------------------------------------------------------------------
# Discovery entities (SIM-UI-100 Section 8.1, produced by SIM-UI-101)
# ---------------------------------------------------------------------------
class AgentDescriptor(BaseModel):
    """A static description of one agent within a simulator."""

    agent_id: str = Field(..., description="Slugified stable id, e.g. 'programmer'")
    agent_name: str = Field(..., description="Human-readable name, e.g. 'Programmer'")
    role: str = Field(..., description="Role/label as defined by the simulator")
    order: int = Field(..., description="Display / execution order (0-based)")
    framework: str = Field("", description="e.g. 'Direct LLM (ChatDev)', 'A2A / LangGraph'")
    description: str = Field("", description="Short description for tooltips")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Tooltip metadata")


class WorkflowDescriptor(BaseModel):
    """A predefined named subset of a simulator's mesh (SIM-UI-101).

    Workflows let a large mesh expose curated sub-graphs (e.g. a
    researcher→analyst→writer pipeline inside a mesh that also holds an
    escalation agent). Launching a workflow sends its ``agent_ids`` as
    ``LaunchRequest.agent_scope``; the rest of the mesh renders as OUT.
    """

    id: str = Field(..., description="Slugified stable id, e.g. 'research_pipeline'")
    name: str = Field(..., description="Human-readable name, e.g. 'Research pipeline'")
    description: str = Field("", description="One-line summary for the picker")
    agent_ids: List[str] = Field(
        ..., description="Roster agent_ids that are in scope for this workflow"
    )


class LaunchSpec(BaseModel):
    """Everything the launcher (SIM-UI-102) needs to start one instance."""

    kind: LaunchKind
    command: str = Field(..., description="Executable, e.g. 'python' or 'bash'")
    args: List[str] = Field(default_factory=list)
    cwd: str = Field(..., description="Working directory (absolute)")
    env_required: List[str] = Field(
        default_factory=list, description="Env vars that must be present"
    )
    requires_start_script: bool = Field(
        False, description="True if a separate start script must run first (manual sims)"
    )
    start_command: Optional[str] = Field(
        None, description="Optional start command (e.g. start_swarm.sh) when required"
    )
    ready_marker: Optional[str] = Field(
        None,
        description="Substring in the start script's output that signals readiness",
    )
    ready_timeout_seconds: int = Field(
        60, description="Max seconds to wait for the start script readiness marker"
    )
    port_base_env: Optional[str] = Field(
        None,
        description="Env var name carrying the per-instance base port (e.g. PORT_BASE)",
    )
    port_base: int = Field(
        9001, description="Default base port for the first instance (index 0)"
    )
    port_stride: int = Field(
        10, description="Port offset applied per instance index"
    )


class Simulator(BaseModel):
    """A discovered simulator and its agent roster (SIM-UI-101 output)."""

    id: str
    name: str
    path: str
    topology: str
    launch: LaunchSpec
    agents: List[AgentDescriptor] = Field(default_factory=list)
    workflows: List[WorkflowDescriptor] = Field(
        default_factory=list,
        description="Predefined agent subsets runnable via agent_scope",
    )


# ---------------------------------------------------------------------------
# Runtime entities (consumed by SIM-UI-102/103/104/105)
# ---------------------------------------------------------------------------
class AgentRuntimeState(BaseModel):
    """Live state of an agent within a running instance (SIM-UI-100 8.1/8.2)."""

    agent_id: str
    agent_name: str
    state: AgentState = AgentState.NOT_STARTED
    in_scope: bool = Field(
        True,
        description=(
            "False when the agent was excluded from the run via LaunchRequest."
            "agent_scope. Out-of-scope agents are not stepped and render as OUT "
            "in the live mesh (excluded from active/done tallies)."
        ),
    )
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    last_event: Optional[str] = None
    failure_modes: List[str] = Field(default_factory=list)


class LaunchRequest(BaseModel):
    """Request to launch N instances of a simulator (SIM-UI-105 POST /api/launch)."""

    simulator_id: str
    concurrency: int
    task_prompt: Optional[str] = None
    agent_scope: Optional[List[str]] = Field(
        None,
        description=(
            "Agent ids (into the simulator roster) to run. None or empty means "
            "run the whole mesh; otherwise agents not listed are marked "
            "out-of-scope and rendered as OUT."
        ),
    )


class InstanceDescriptor(BaseModel):
    """A single launched instance and its agents' runtime states."""

    instance_id: str
    run_group_id: str
    simulator_id: str
    index: int
    status: InstanceStatus = InstanceStatus.PENDING
    agents: List[AgentRuntimeState] = Field(default_factory=list)


class LaunchResponse(BaseModel):
    """Result of a launch: the group id and its instances."""

    run_group_id: str
    instances: List[InstanceDescriptor] = Field(default_factory=list)


class StateChangeEvent(BaseModel):
    """Emitted by the state tracker (SIM-UI-103) on every transition."""

    instance_id: str
    run_group_id: str
    agent_id: str
    agent_name: str
    old_state: AgentState
    new_state: AgentState
    ts: datetime
    failure_modes: List[str] = Field(default_factory=list)


class LogLine(BaseModel):
    """One captured log line for an instance (SIM-UI-104)."""

    ts: datetime
    agent_id: Optional[str] = None
    level: str = "INFO"
    message: str


class RunLog(BaseModel):
    """The persisted log for one instance (SIM-UI-104)."""

    instance_id: str
    simulator_id: str
    created_at: datetime
    lines: List[LogLine] = Field(default_factory=list)
