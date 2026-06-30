"""Tests for SIM-UI-102 Simulation Launcher.

Covers SCENARIO-102-01 .. SCENARIO-102-07 using stub simulators (trivial
scripts) so the tests are deterministic and require no LLM credentials.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

import pytest

from app.config import Settings
from app.discovery.registry import SimulatorRegistry, SimulatorRegistryInterface
from app.launcher import SimulationLauncher
from app.launcher.sinks import LaunchSink
from app.models import (
    AgentDescriptor,
    InstanceStatus,
    LaunchKind,
    LaunchRequest,
    LaunchSpec,
    Simulator,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class FakeRegistry(SimulatorRegistryInterface):
    def __init__(self, sims: List[Simulator]):
        self._sims = {s.id: s for s in sims}

    def list_all(self):
        return list(self._sims.values())

    def get(self, simulator_id):
        return self._sims.get(simulator_id)

    def get_agents(self, simulator_id):
        s = self.get(simulator_id)
        return s.agents if s else []

    def reload(self):
        pass


class RecordingSink(LaunchSink):
    def __init__(self):
        self.lines: List[tuple] = []
        self.exits: List[tuple] = []

    async def on_log_line(self, instance_id, line):
        self.lines.append((instance_id, line))

    async def on_instance_exit(self, instance_id, return_code, status):
        self.exits.append((instance_id, return_code, status))


def _agents(n: int) -> List[AgentDescriptor]:
    return [
        AgentDescriptor(agent_id=f"a{i}", agent_name=f"A{i}", role=f"a{i}", order=i)
        for i in range(n)
    ]


def _write(path: Path, content: str, executable: bool = False) -> Path:
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)
    return path


def _python_stub(tmp: Path, duration: float) -> Path:
    return _write(
        tmp / "stub.py",
        "import sys, time\n"
        "dur = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0\n"
        "print('stub start', flush=True)\n"
        "time.sleep(dur)\n"
        "print('stub done', flush=True)\n",
    )


def _python_sim(
    sim_id: str,
    stub: Path,
    duration: float,
    n_agents: int = 3,
    env_required: Optional[List[str]] = None,
) -> Simulator:
    spec = LaunchSpec(
        kind=LaunchKind.PYTHON,
        command="python",
        args=[str(stub), str(duration)],
        cwd=str(stub.parent),
        env_required=env_required or [],
    )
    return Simulator(
        id=sim_id, name=sim_id, path=str(stub.parent),
        topology="stub", launch=spec, agents=_agents(n_agents),
    )


def _settings(tmp: Path, max_concurrency: int = 32) -> Settings:
    # Override attributes directly to avoid leaking env vars across tests.
    s = Settings()
    s.repo_root = tmp
    s.simulators_dir = tmp / "simulators"
    s.max_concurrency = max_concurrency
    return s


async def _await_group_done(launcher, group_id, timeout=15.0):
    terminal = {InstanceStatus.COMPLETED, InstanceStatus.FAILED, InstanceStatus.CANCELLED}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = [d.status for d in launcher.get_group(group_id)]
        if statuses and all(s in terminal for s in statuses):
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"group did not finish: {[d.status for d in launcher.get_group(group_id)]}")


# ---------------------------------------------------------------------------
# SCENARIO-102-01: Launch N python instances
# ---------------------------------------------------------------------------
def test_launch_n_instances_running(tmp_path):
    async def run():
        stub = _python_stub(tmp_path, duration=3.0)
        # chatdev agents (6) but stub process — faithful to scenario, deterministic.
        real = SimulatorRegistry(settings=Settings())
        chatdev_agents = real.get_agents("chatdev")
        sim = _python_sim("chatdev", stub, 3.0)
        sim.agents = chatdev_agents
        launcher = SimulationLauncher(FakeRegistry([sim]), settings=_settings(tmp_path))

        resp = await launcher.launch(LaunchRequest(simulator_id="chatdev", concurrency=2))
        assert resp.run_group_id
        assert len(resp.instances) == 2
        ids = {i.instance_id for i in resp.instances}
        assert len(ids) == 2  # unique
        for inst in resp.instances:
            assert inst.status == InstanceStatus.RUNNING
            assert len(inst.agents) == 6
            mi = launcher._instances[inst.instance_id]
            assert mi.proc is not None and mi.proc.returncode is None  # live subprocess
        await launcher.cancel(resp.run_group_id)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SCENARIO-102-02: Correct cwd/PYTHONPATH for python entrypoint (real registry)
# ---------------------------------------------------------------------------
def test_python_entrypoint_cwd_and_pythonpath():
    settings = Settings()
    launcher = SimulationLauncher(SimulatorRegistry(settings=settings), settings=settings)
    plan = launcher.plan_run("chatdev")
    assert plan.cwd.replace("\\", "/").endswith("simulators/chatdev")
    assert "PYTHONPATH" in plan.env
    assert str(settings.repo_root) in plan.env["PYTHONPATH"]
    # invocation uses this interpreter + the entrypoint
    assert plan.argv[0] == sys.executable
    assert plan.argv[-1].endswith("run_chatdev_sim.py")


# ---------------------------------------------------------------------------
# SCENARIO-102-03: Bash start -> ready -> run ordering
# ---------------------------------------------------------------------------
def test_bash_start_then_run_ordering(tmp_path):
    async def run():
        start = _write(
            tmp_path / "start.sh",
            "#!/usr/bin/env bash\necho 'starting servers'\necho 'agents up'\nsleep 0.3\n",
            executable=True,
        )
        runsh = _write(
            tmp_path / "run.sh",
            "#!/usr/bin/env bash\necho 'running pipeline'\necho 'pipeline done'\n",
            executable=True,
        )
        spec = LaunchSpec(
            kind=LaunchKind.BASH, command="bash", args=[str(runsh)],
            cwd=str(tmp_path), requires_start_script=True, start_command=str(start),
            ready_marker="up", ready_timeout_seconds=10, port_base_env="PORT_BASE",
        )
        sim = Simulator(id="manual-swarm", name="m", path=str(tmp_path),
                        topology="p2p", launch=spec, agents=_agents(3))
        sink = RecordingSink()
        launcher = SimulationLauncher(FakeRegistry([sim]), settings=_settings(tmp_path), sink=sink)

        resp = await launcher.launch(LaunchRequest(simulator_id="manual-swarm", concurrency=1))
        await _await_group_done(launcher, resp.run_group_id)

        assert launcher.get_group(resp.run_group_id)[0].status == InstanceStatus.COMPLETED
        texts = [l for _, l in sink.lines]
        assert "agents up" in texts
        assert "running pipeline" in texts
        assert texts.index("agents up") < texts.index("running pipeline")

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SCENARIO-102-04: Port isolation for parallel manual instances (real registry)
# ---------------------------------------------------------------------------
def test_port_isolation_per_instance():
    settings = Settings()
    launcher = SimulationLauncher(SimulatorRegistry(settings=settings), settings=settings)
    p0 = launcher.plan_run("manual-swarm", index=0)
    p1 = launcher.plan_run("manual-swarm", index=1)
    assert p0.env["PORT_BASE"] != p1.env["PORT_BASE"]
    assert p0.port_base == 9001 and p1.port_base == 9011


# ---------------------------------------------------------------------------
# SCENARIO-102-05: Missing provider config fails fast, doesn't block others
# ---------------------------------------------------------------------------
def test_missing_env_fails_fast(tmp_path):
    async def run():
        stub = _python_stub(tmp_path, duration=0.2)
        bad = _python_sim("bad", stub, 0.2, env_required=["AGENT_SIM_TEST_MISSING_VAR"])
        good = _python_sim("good", stub, 0.2)
        launcher = SimulationLauncher(FakeRegistry([bad, good]), settings=_settings(tmp_path))

        resp = await launcher.launch(LaunchRequest(simulator_id="bad", concurrency=3))
        await _await_group_done(launcher, resp.run_group_id, timeout=5)
        for inst in launcher.get_group(resp.run_group_id):
            assert inst.status == InstanceStatus.FAILED
            mi = launcher._instances[inst.instance_id]
            assert "AGENT_SIM_TEST_MISSING_VAR" in (mi.error_reason or "")

        # launcher still usable for a healthy simulator afterwards
        resp2 = await launcher.launch(LaunchRequest(simulator_id="good", concurrency=2))
        await _await_group_done(launcher, resp2.run_group_id, timeout=10)
        assert all(i.status == InstanceStatus.COMPLETED for i in launcher.get_group(resp2.run_group_id))

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SCENARIO-102-06: Cancellation kills all children (incl. started servers)
# ---------------------------------------------------------------------------
def test_cancel_kills_all_children(tmp_path):
    async def run():
        pid_file = tmp_path / "server.pid"
        os.environ["SERVER_PID_FILE"] = str(pid_file)
        start = _write(
            tmp_path / "start.sh",
            "#!/usr/bin/env bash\n"
            "sleep 300 &\n"
            'echo $! > "$SERVER_PID_FILE"\n'
            "echo 'agents up'\n"
            "sleep 300\n",
            executable=True,
        )
        runsh = _write(tmp_path / "run.sh", "#!/usr/bin/env bash\nsleep 300\n", executable=True)
        spec = LaunchSpec(
            kind=LaunchKind.BASH, command="bash", args=[str(runsh)],
            cwd=str(tmp_path), requires_start_script=True, start_command=str(start),
            ready_marker="up", ready_timeout_seconds=10,
        )
        sim = Simulator(id="manual-swarm", name="m", path=str(tmp_path),
                        topology="p2p", launch=spec, agents=_agents(3))
        launcher = SimulationLauncher(FakeRegistry([sim]), settings=_settings(tmp_path))

        resp = await launcher.launch(LaunchRequest(simulator_id="manual-swarm", concurrency=1))
        inst = resp.instances[0]
        assert inst.status == InstanceStatus.RUNNING

        # wait until the start script recorded its background server pid
        for _ in range(50):
            if pid_file.is_file() and pid_file.read_text().strip():
                break
            await asyncio.sleep(0.05)
        server_pid = int(pid_file.read_text().strip())

        await launcher.cancel(resp.run_group_id)
        await asyncio.sleep(0.3)

        assert launcher.get_instance(inst.instance_id).status == InstanceStatus.CANCELLED
        # server child must be dead
        dead = False
        for _ in range(40):
            try:
                os.kill(server_pid, 0)
                await asyncio.sleep(0.05)
            except ProcessLookupError:
                dead = True
                break
        assert dead, f"server pid {server_pid} still alive after cancel"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SCENARIO-102-07: Concurrency bound queues excess
# ---------------------------------------------------------------------------
def test_concurrency_bound_queues_excess(tmp_path):
    async def run():
        stub = _python_stub(tmp_path, duration=1.5)
        sim = _python_sim("chatdev", stub, 1.5)
        launcher = SimulationLauncher(FakeRegistry([sim]), settings=_settings(tmp_path, max_concurrency=4))
        assert launcher.bound == 4

        resp = await launcher.launch(LaunchRequest(simulator_id="chatdev", concurrency=10))
        running = [i for i in launcher.get_group(resp.run_group_id) if i.status == InstanceStatus.RUNNING]
        pending = [i for i in launcher.get_group(resp.run_group_id) if i.status == InstanceStatus.PENDING]
        assert len(running) == 4
        assert len(pending) == 6

        await _await_group_done(launcher, resp.run_group_id, timeout=30)
        assert all(i.status == InstanceStatus.COMPLETED for i in launcher.get_group(resp.run_group_id))

    asyncio.run(run())
