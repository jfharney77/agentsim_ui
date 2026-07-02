"""SimulationLauncher — process orchestration (SIM-UI-102).

Starts a selected simulator N times in parallel as independent OS processes,
tracks each instance in-memory, captures and forwards their output, bounds total
concurrency with a worker pool, and cleans everything up on cancel.

Design notes
------------
* Each instance runs in its own process *session* (``start_new_session=True``)
  so we can terminate the whole process group — including agent servers started
  by manual simulators — with a single ``killpg``.
* A global semaphore-like counter (``_running_count`` vs ``bound``) limits how
  many instances run at once. Excess instances sit in ``_pending`` and are
  promoted as slots free up.
* Output is read line-by-line off the merged stdout/stderr pipe and fanned out
  to sinks (SIM-UI-103 state tracker, SIM-UI-104 logger).
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional

from ..config import Settings, get_settings
from ..discovery.registry import SimulatorRegistryInterface
from ..models import (
    AgentRuntimeState,
    InstanceDescriptor,
    InstanceStatus,
    LaunchKind,
    LaunchRequest,
    LaunchResponse,
    LaunchSpec,
    Simulator,
)
from .sinks import CompositeSink, LaunchSink

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dotenv(path: Path) -> Dict[str, str]:
    """Minimal .env parser: ``KEY=VALUE`` lines, ignoring comments/blanks."""
    env: Dict[str, str] = {}
    if not path.is_file():
        return env
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                env[key] = value
    except OSError:
        logger.warning("could not read .env at %s", path)
    return env


@dataclass
class RunPlan:
    """The concrete invocation for one instance's main process."""

    argv: List[str]
    cwd: str
    env: Dict[str, str]
    port_base: Optional[int] = None

    def start_argv(self, start_command: str) -> List[str]:
        """argv for the start script (manual sims), reusing this plan's shell."""
        return ["bash", start_command]


@dataclass
class InstanceProcess:
    """Runtime handle for one instance (SIM-UI-102 Data Model)."""

    instance_id: str
    pid: Optional[int] = None
    child_pids: List[int] = field(default_factory=list)
    port_offset: Optional[int] = None
    status: InstanceStatus = InstanceStatus.PENDING
    return_code: Optional[int] = None


@dataclass
class _Managed:
    """Internal bookkeeping for a managed instance."""

    descriptor: InstanceDescriptor
    simulator: Simulator
    task_prompt: Optional[str]
    plan: RunPlan
    proc: Optional[asyncio.subprocess.Process] = None
    start_proc: Optional[asyncio.subprocess.Process] = None
    supervise_task: Optional[asyncio.Task] = None
    drain_task: Optional[asyncio.Task] = None
    cancel_requested: bool = False
    error_reason: Optional[str] = None
    handle: InstanceProcess = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.handle is None:
            self.handle = InstanceProcess(instance_id=self.descriptor.instance_id)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
class SimulationLauncherInterface:
    async def launch(self, request: LaunchRequest) -> LaunchResponse:
        raise NotImplementedError

    def get_instance(self, instance_id: str) -> Optional[InstanceDescriptor]:
        raise NotImplementedError

    def get_group(self, run_group_id: str) -> List[InstanceDescriptor]:
        raise NotImplementedError

    async def cancel(self, run_group_id: str) -> None:
        raise NotImplementedError

    def list_active(self) -> List[InstanceDescriptor]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------
class SimulationLauncher(SimulationLauncherInterface):
    def __init__(
        self,
        registry: SimulatorRegistryInterface,
        settings: Optional[Settings] = None,
        sink: Optional[LaunchSink] = None,
    ) -> None:
        self._registry = registry
        self._settings = settings or get_settings()
        self._sink: LaunchSink = sink or CompositeSink()
        self.bound = max(1, int(self._settings.max_concurrency))

        self._instances: Dict[str, _Managed] = {}
        self._groups: Dict[str, List[str]] = {}
        self._pending: Deque[_Managed] = deque()
        self._running_count = 0
        self._lock = asyncio.Lock()
        self._dotenv = parse_dotenv(self._settings.repo_root / ".env")

    # -- public API --------------------------------------------------------
    async def launch(self, request: LaunchRequest) -> LaunchResponse:
        if request.concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        sim = self._registry.get(request.simulator_id)
        if sim is None:
            raise KeyError(f"unknown simulator_id: {request.simulator_id}")

        run_group_id = str(uuid.uuid4())
        managed: List[_Managed] = []
        for index in range(request.concurrency):
            mi = self._make_instance(
                sim, run_group_id, index, request.task_prompt, request.agent_scope
            )
            self._instances[mi.descriptor.instance_id] = mi
            managed.append(mi)
        self._groups[run_group_id] = [m.descriptor.instance_id for m in managed]

        for mi in managed:
            await self._sink.on_instance_created(mi.descriptor)
            self._pending.append(mi)

        await self._fill_slots(await_spawn=True)

        return LaunchResponse(
            run_group_id=run_group_id,
            instances=[m.descriptor for m in managed],
        )

    def get_instance(self, instance_id: str) -> Optional[InstanceDescriptor]:
        mi = self._instances.get(instance_id)
        return mi.descriptor if mi else None

    def get_group(self, run_group_id: str) -> List[InstanceDescriptor]:
        return [
            self._instances[i].descriptor
            for i in self._groups.get(run_group_id, [])
            if i in self._instances
        ]

    def list_active(self) -> List[InstanceDescriptor]:
        active = {InstanceStatus.PENDING, InstanceStatus.RUNNING}
        return [m.descriptor for m in self._instances.values() if m.descriptor.status in active]

    async def cancel(self, run_group_id: str) -> None:
        ids = list(self._groups.get(run_group_id, []))
        for instance_id in ids:
            mi = self._instances.get(instance_id)
            if mi is None:
                continue
            mi.cancel_requested = True
            self._kill_process_tree(mi)
            if mi.descriptor.status in (InstanceStatus.PENDING,):
                self._set_status(mi, InstanceStatus.CANCELLED, fire=True)

        # Give supervisors a moment to observe termination and finalize.
        await asyncio.sleep(0)
        for instance_id in ids:
            mi = self._instances.get(instance_id)
            if mi and mi.descriptor.status in (InstanceStatus.RUNNING,):
                self._set_status(mi, InstanceStatus.CANCELLED, fire=True)

    # -- run planning (testable, side-effect free) -------------------------
    def plan_run(self, simulator_id: str, index: int = 0, task_prompt: Optional[str] = None) -> RunPlan:
        sim = self._registry.get(simulator_id)
        if sim is None:
            raise KeyError(f"unknown simulator_id: {simulator_id}")
        return self._build_plan(sim, index, task_prompt)

    # -- internals ---------------------------------------------------------
    def _make_instance(
        self,
        sim: Simulator,
        run_group_id: str,
        index: int,
        task_prompt: Optional[str],
        agent_scope: Optional[List[str]] = None,
    ) -> _Managed:
        instance_id = str(uuid.uuid4())
        # An empty/None scope means "run the whole mesh"; otherwise only the
        # listed agent ids are in scope and the rest render as OUT.
        scope: Optional[set] = set(agent_scope) if agent_scope else None
        agents = [
            AgentRuntimeState(
                agent_id=a.agent_id,
                agent_name=a.agent_name,
                in_scope=scope is None or a.agent_id in scope,
            )
            for a in sim.agents
        ]
        descriptor = InstanceDescriptor(
            instance_id=instance_id,
            run_group_id=run_group_id,
            simulator_id=sim.id,
            index=index,
            status=InstanceStatus.PENDING,
            agents=agents,
        )
        plan = self._build_plan(sim, index, task_prompt)
        return _Managed(
            descriptor=descriptor,
            simulator=sim,
            task_prompt=task_prompt,
            plan=plan,
        )

    def _build_plan(self, sim: Simulator, index: int, task_prompt: Optional[str]) -> RunPlan:
        spec = sim.launch
        env = self._build_env(spec, index)
        argv = self._resolve_argv(spec, task_prompt)
        port_base = None
        if spec.port_base_env:
            port_base = spec.port_base + index * spec.port_stride
        return RunPlan(argv=argv, cwd=spec.cwd, env=env, port_base=port_base)

    def _resolve_argv(self, spec: LaunchSpec, task_prompt: Optional[str]) -> List[str]:
        command = sys.executable if spec.command == "python" else spec.command
        argv = [command, *spec.args]
        # Pass the task prompt to simulators that accept a positional topic/task
        # (manual run_*.sh scripts and the hyperagent runner).
        if task_prompt:
            argv.append(task_prompt)
        return argv

    def _build_env(self, spec: LaunchSpec, index: int) -> Dict[str, str]:
        env = dict(os.environ)
        for key, value in self._dotenv.items():
            env.setdefault(key, value)

        repo_root = str(self._settings.repo_root)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            repo_root + (os.pathsep + existing if existing else "")
        )

        if spec.port_base_env:
            env[spec.port_base_env] = str(spec.port_base + index * spec.port_stride)
        return env

    async def _fill_slots(self, await_spawn: bool) -> None:
        to_start: List[_Managed] = []
        async with self._lock:
            while self._running_count < self.bound and self._pending:
                mi = self._pending.popleft()
                if mi.cancel_requested:
                    self._set_status(mi, InstanceStatus.CANCELLED, fire=True)
                    continue
                self._running_count += 1
                to_start.append(mi)

        coros = [self._start_instance(mi) for mi in to_start]
        if not coros:
            return
        if await_spawn:
            await asyncio.gather(*coros)
        else:
            for c in coros:
                asyncio.create_task(c)

    async def _start_instance(self, mi: _Managed) -> None:
        try:
            spec = mi.simulator.launch
            plan = mi.plan
            mi.handle.port_offset = plan.port_base

            missing = [v for v in spec.env_required if not plan.env.get(v)]
            if missing:
                self._fail(mi, f"missing required env var(s): {', '.join(missing)}")
                await self._release_slot()
                return

            if spec.requires_start_script and spec.start_command:
                ok = await self._start_servers(mi, spec, plan)
                if not ok:
                    self._fail(mi, "start script did not become ready in time")
                    self._kill_process_tree(mi)
                    await self._release_slot()
                    return

            proc = await asyncio.create_subprocess_exec(
                *plan.argv,
                cwd=plan.cwd,
                env=plan.env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            mi.proc = proc
            mi.handle.pid = proc.pid
            self._set_status(mi, InstanceStatus.RUNNING, fire=True)
            mi.descriptor.agents = mi.descriptor.agents  # keep states
            await self._sink.on_instance_start(mi.descriptor)
            mi.supervise_task = asyncio.create_task(self._supervise(mi, proc))
        except Exception as exc:  # noqa: BLE001 - one instance must not break others
            logger.exception("failed to start instance %s", mi.descriptor.instance_id)
            self._fail(mi, f"spawn error: {exc}")
            self._kill_process_tree(mi)
            await self._release_slot()

    async def _start_servers(self, mi: _Managed, spec: LaunchSpec, plan: RunPlan) -> bool:
        start_proc = await asyncio.create_subprocess_exec(
            "bash",
            spec.start_command,
            cwd=plan.cwd,
            env=plan.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        mi.start_proc = start_proc
        if start_proc.pid:
            mi.handle.child_pids.append(start_proc.pid)

        ready = await self._await_ready(mi, start_proc, spec)
        # Keep draining the start process output in the background.
        mi.drain_task = asyncio.create_task(self._drain(mi, start_proc))
        return ready

    async def _await_ready(self, mi: _Managed, proc: asyncio.subprocess.Process, spec: LaunchSpec) -> bool:
        marker = spec.ready_marker
        if not marker:
            return True
        deadline = asyncio.get_event_loop().time() + spec.ready_timeout_seconds

        async def _scan() -> bool:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    return False
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                await self._sink.on_log_line(mi.descriptor.instance_id, text)
                if marker.lower() in text.lower():
                    return True

        try:
            timeout = max(0.0, deadline - asyncio.get_event_loop().time())
            return await asyncio.wait_for(_scan(), timeout=timeout)
        except asyncio.TimeoutError:
            return False

    async def _drain(self, mi: _Managed, proc: asyncio.subprocess.Process) -> None:
        if proc.stdout is None:
            return
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                await self._sink.on_log_line(mi.descriptor.instance_id, text)
        except Exception:  # noqa: BLE001
            pass

    async def _supervise(self, mi: _Managed, proc: asyncio.subprocess.Process) -> None:
        try:
            if proc.stdout is not None:
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip("\n")
                    await self._sink.on_log_line(mi.descriptor.instance_id, text)
            return_code = await proc.wait()
        except Exception as exc:  # noqa: BLE001
            logger.exception("supervise error for %s", mi.descriptor.instance_id)
            return_code = -1
            mi.error_reason = str(exc)
        finally:
            # Tear down any auxiliary servers started for this instance.
            self._kill_start_proc(mi)

        mi.handle.return_code = return_code
        self._finalize(mi, return_code)
        await self._sink.on_instance_exit(
            mi.descriptor.instance_id, return_code, mi.descriptor.status
        )
        await self._release_slot()

    def _finalize(self, mi: _Managed, return_code: int) -> None:
        if mi.cancel_requested:
            self._set_status(mi, InstanceStatus.CANCELLED, fire=True)
        elif return_code == 0:
            self._set_status(mi, InstanceStatus.COMPLETED, fire=True)
        else:
            self._set_status(mi, InstanceStatus.FAILED, fire=True)

    async def _release_slot(self) -> None:
        async with self._lock:
            self._running_count = max(0, self._running_count - 1)
        await self._fill_slots(await_spawn=False)

    def _fail(self, mi: _Managed, reason: str) -> None:
        mi.error_reason = reason
        logger.warning("instance %s failed: %s", mi.descriptor.instance_id, reason)
        self._set_status(mi, InstanceStatus.FAILED, fire=True)

    def _set_status(self, mi: _Managed, status: InstanceStatus, fire: bool = False) -> None:
        if mi.descriptor.status == status:
            return
        mi.descriptor.status = status
        mi.handle.status = status
        if fire:
            # Fire-and-forget status notification (best effort, non-blocking).
            try:
                asyncio.get_running_loop().create_task(
                    self._sink.on_status_change(mi.descriptor.instance_id, status)
                )
            except RuntimeError:
                pass

    # -- process teardown --------------------------------------------------
    def _kill_process_tree(self, mi: _Managed) -> None:
        self._kill_proc(mi.proc)
        self._kill_start_proc(mi)

    def _kill_start_proc(self, mi: _Managed) -> None:
        if mi.start_proc is not None:
            self._kill_proc(mi.start_proc)
            mi.start_proc = None

    @staticmethod
    def _kill_proc(proc: Optional[asyncio.subprocess.Process]) -> None:
        if proc is None or proc.returncode is not None:
            return
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
