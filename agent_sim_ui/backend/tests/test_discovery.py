"""Tests for SIM-UI-101 Simulator & Agent Discovery.

Covers SCENARIO-101-01 .. SCENARIO-101-07. The "happy path" scenarios run
against the real ``simulators/`` tree in the repo; the fallback scenario uses a
synthetic temp repo root so no real files are mutated.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.discovery.registry import SimulatorRegistry
from app.models import AgentDescriptor


@pytest.fixture()
def registry() -> SimulatorRegistry:
    """Registry bound to the real repo (auto-detected root)."""
    return SimulatorRegistry(settings=Settings())


EXPECTED_IDS = {
    "chatdev",
    "metagpt",
    "manual-swarm",
    "manual-orchestrator",
    "hyperagent",
}


# --- SCENARIO-101-01 -------------------------------------------------------
def test_discover_all_five_simulators(registry: SimulatorRegistry):
    ids = {sim.id for sim in registry.list_all()}
    assert ids == EXPECTED_IDS


# --- SCENARIO-101-02 -------------------------------------------------------
def test_chatdev_roster_from_roleconfig(registry: SimulatorRegistry):
    agents = registry.get_agents("chatdev")
    names = [a.agent_name for a in agents]
    assert len(agents) == 6
    assert names[0] == "Chief Executive Officer"
    assert "Programmer" in names
    # order is preserved and 0-based
    assert [a.order for a in agents] == list(range(6))


# --- SCENARIO-101-03 -------------------------------------------------------
def test_metagpt_roster_order(registry: SimulatorRegistry):
    names = [a.agent_name for a in registry.get_agents("metagpt")]
    assert names == [
        "Product Manager",
        "Architect",
        "Project Manager",
        "Engineer",
        "QA Engineer",
    ]


# --- SCENARIO-101-04 -------------------------------------------------------
def test_manual_swarm_roster(registry: SimulatorRegistry):
    roles = [a.role for a in registry.get_agents("manual-swarm")]
    assert roles == ["analyst", "researcher", "writer"] or sorted(roles) == [
        "analyst",
        "researcher",
        "writer",
    ]
    assert {a.agent_name for a in registry.get_agents("manual-swarm")} == {
        "Analyst",
        "Researcher",
        "Writer",
    }


# --- SCENARIO-101-05 -------------------------------------------------------
def test_hyperagent_roster_order(registry: SimulatorRegistry):
    roles = [a.role for a in registry.get_agents("hyperagent")]
    assert roles == ["planner", "navigator", "editor", "executor"]


# --- SCENARIO-101-06 -------------------------------------------------------
def test_fallback_when_source_missing(monkeypatch, tmp_path):
    """With RoleConfig.json absent, chatdev still yields its 6-agent fallback."""
    # Synthetic repo: simulators/chatdev exists but has no config/RoleConfig.json
    (tmp_path / "simulators" / "chatdev").mkdir(parents=True)

    monkeypatch.setenv("AGENT_SIM_REPO_ROOT", str(tmp_path))
    settings = Settings()
    reg = SimulatorRegistry(settings=settings)

    agents = reg.get_agents("chatdev")
    assert len(agents) == 6
    assert agents[0].agent_name == "Chief Executive Officer"
    # Only chatdev exists in this synthetic tree
    assert {s.id for s in reg.list_all()} == {"chatdev"}


# --- SCENARIO-101-07 -------------------------------------------------------
def test_agent_descriptor_metadata_populated(registry: SimulatorRegistry):
    for sim in registry.list_all():
        assert sim.agents, f"{sim.id} has no agents"
        for agent in sim.agents:
            assert isinstance(agent, AgentDescriptor)
            assert agent.agent_id
            assert agent.agent_name
            assert agent.order >= 0
            assert "topology" in agent.metadata
            assert "framework" in agent.metadata
            assert agent.metadata["simulator_id"] == sim.id


def test_launch_spec_present_for_each_simulator(registry: SimulatorRegistry):
    for sim in registry.list_all():
        assert sim.launch is not None
        assert sim.launch.command in ("python", "bash")
        assert sim.launch.cwd


def test_reload_rebuilds_cache(registry: SimulatorRegistry):
    first = registry.list_all()
    registry.reload()
    second = registry.list_all()
    assert {s.id for s in first} == {s.id for s in second}
