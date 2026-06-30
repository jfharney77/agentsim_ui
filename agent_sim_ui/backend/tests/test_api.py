"""Integration tests for SIM-UI-105 FastAPI Backend API.

Covers SCENARIO-105-01 .. SCENARIO-105-09. Discovery endpoints use the real
registry; launching uses a stub simulator (a trivial python script) so no real
simulators or LLM credentials are required.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import create_app
from app.config import Settings
from app.discovery.registry import SimulatorRegistry, SimulatorRegistryInterface
from app.launcher import CompositeSink, SimulationLauncher
from app.models import LaunchKind, LaunchSpec, Simulator
from app.storage import RunStore
from app.tracking import StateTracker


class FakeRegistry(SimulatorRegistryInterface):
    def __init__(self, sims):
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


def _stub_script(tmp: Path) -> Path:
    p = tmp / "stub.py"
    p.write_text(
        "import sys, time\n"
        "dur = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0\n"
        "print('stub start', flush=True)\n"
        "time.sleep(dur)\n"
        "print('stub done', flush=True)\n",
        encoding="utf-8",
    )
    return p


def build_app(tmp_path: Path, duration: float = 0.3):
    """Real registry for discovery; stub launcher for launching."""
    settings = Settings()
    settings.repo_root = tmp_path
    settings.simulators_dir = tmp_path / "simulators"
    settings.db_path = tmp_path / "api.db"
    settings.max_concurrency = 16

    real = SimulatorRegistry(settings=Settings())
    stub = _stub_script(tmp_path)
    chatdev = Simulator(
        id="chatdev", name="ChatDev (stub)", path=str(tmp_path), topology="stub",
        launch=LaunchSpec(
            kind=LaunchKind.PYTHON, command="python",
            args=[str(stub), str(duration)], cwd=str(tmp_path), env_required=[],
        ),
        agents=real.get_agents("chatdev"),
    )
    tracker = StateTracker()
    store = RunStore(settings=settings, db_path=settings.db_path)
    launcher = SimulationLauncher(
        FakeRegistry([chatdev]), settings=settings, sink=CompositeSink([tracker, store])
    )
    app = create_app(
        settings=settings, registry=real, launcher=launcher, tracker=tracker, store=store
    )
    return app, tracker, store


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _wait_status(ac, run_group_id, predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = await ac.get(f"/api/runs/{run_group_id}")
        if r.status_code == 200 and predicate(r.json()["instances"]):
            return r.json()["instances"]
        await asyncio.sleep(0.05)
    raise AssertionError("status predicate not met in time")


# --- SCENARIO-105-01 -------------------------------------------------------
def test_list_simulators_with_agents(tmp_path):
    async def run():
        app, _, _ = build_app(tmp_path)
        async with _client(app) as ac:
            r = await ac.get("/api/simulators")
            assert r.status_code == 200
            sims = r.json()
            assert len(sims) == 5
            chatdev = next(s for s in sims if s["id"] == "chatdev")
            assert len(chatdev["agents"]) == 6

    asyncio.run(run())


# --- SCENARIO-105-02 -------------------------------------------------------
def test_launch_returns_group_and_instances(tmp_path):
    async def run():
        app, _, _ = build_app(tmp_path, duration=2.0)
        async with _client(app) as ac:
            r = await ac.post("/api/launch", json={"simulator_id": "chatdev", "concurrency": 2})
            assert r.status_code == 200
            d = r.json()
            assert d["run_group_id"]
            assert len(d["instances"]) == 2
            ids = {i["instance_id"] for i in d["instances"]}
            assert len(ids) == 2
            await ac.post(f"/api/runs/{d['run_group_id']}/cancel")

    asyncio.run(run())


# --- SCENARIO-105-03 -------------------------------------------------------
def test_invalid_simulator_rejected(tmp_path):
    async def run():
        app, _, _ = build_app(tmp_path)
        async with _client(app) as ac:
            r = await ac.post("/api/launch", json={"simulator_id": "bogus", "concurrency": 1})
            assert r.status_code == 404

    asyncio.run(run())


# --- SCENARIO-105-04 -------------------------------------------------------
def test_disallowed_concurrency_rejected(tmp_path):
    async def run():
        app, _, _ = build_app(tmp_path)
        async with _client(app) as ac:
            r = await ac.post("/api/launch", json={"simulator_id": "chatdev", "concurrency": 7})
            assert r.status_code == 400

    asyncio.run(run())


# --- SCENARIO-105-05 -------------------------------------------------------
def test_snapshot_reflects_state(tmp_path):
    async def run():
        app, tracker, _ = build_app(tmp_path, duration=3.0)
        async with _client(app) as ac:
            r = await ac.post("/api/launch", json={"simulator_id": "chatdev", "concurrency": 1})
            d = r.json()
            inst_id = d["instances"][0]["instance_id"]
            tracker.process_line(
                inst_id,
                "[2025-06-28 15:00:00 INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**",
            )
            r2 = await ac.get(f"/api/runs/{d['run_group_id']}")
            agents = r2.json()["instances"][0]["agents"]
            prog = next(a for a in agents if a["agent_id"] == "programmer")
            assert prog["state"] == "running"
            await ac.post(f"/api/runs/{d['run_group_id']}/cancel")

    asyncio.run(run())


def _events_endpoint(app):
    route = next(
        r for r in app.routes
        if getattr(r, "path", None) == "/api/runs/{run_group_id}/events"
    )
    return route.endpoint


# --- SCENARIO-105-06 -------------------------------------------------------
def test_event_stream_emits_transitions(tmp_path):
    # httpx ASGITransport buffers full responses and cannot consume an infinite
    # SSE stream, so we exercise the endpoint closure's StreamingResponse
    # directly (same subscribe + SSE formatting the HTTP route uses).
    async def run():
        app, tracker, _ = build_app(tmp_path, duration=5.0)
        async with _client(app) as ac:
            r = await ac.post("/api/launch", json={"simulator_id": "chatdev", "concurrency": 1})
            d = r.json()
            gid, inst_id = d["run_group_id"], d["instances"][0]["instance_id"]

            response = await _events_endpoint(app)(run_group_id=gid)
            assert response.media_type == "text/event-stream"
            body = response.body_iterator

            async def trigger():
                await asyncio.sleep(0.3)
                tracker.process_line(
                    inst_id,
                    "[INFO] Programmer: **Programmer<->Code Reviewer on : Coding, turn 1**",
                )

            task = asyncio.create_task(trigger())
            chunk = await asyncio.wait_for(body.__anext__(), timeout=4.0)
            await task
            assert chunk.startswith("data:")
            payload = json.loads(chunk[len("data:"):].strip())
            assert payload["new_state"] == "running"
            assert payload["agent_id"] == "programmer"

            await body.aclose()
            await ac.post(f"/api/runs/{gid}/cancel")

    asyncio.run(run())


# --- SCENARIO-105-07 -------------------------------------------------------
def test_log_endpoint_returns_instance_log(tmp_path):
    async def run():
        app, _, _ = build_app(tmp_path, duration=0.3)
        async with _client(app) as ac:
            r = await ac.post("/api/launch", json={"simulator_id": "chatdev", "concurrency": 1})
            d = r.json()
            gid = d["run_group_id"]
            inst_id = d["instances"][0]["instance_id"]
            await _wait_status(ac, gid, lambda insts: all(i["status"] == "completed" for i in insts))
            r2 = await ac.get(f"/api/instances/{inst_id}/log")
            assert r2.status_code == 200
            messages = [ln["message"] for ln in r2.json()["lines"]]
            assert "stub start" in messages and "stub done" in messages

    asyncio.run(run())


# --- SCENARIO-105-08 -------------------------------------------------------
def test_cancel_stops_the_group(tmp_path):
    async def run():
        app, _, _ = build_app(tmp_path, duration=30.0)
        async with _client(app) as ac:
            r = await ac.post("/api/launch", json={"simulator_id": "chatdev", "concurrency": 2})
            gid = r.json()["run_group_id"]
            rc = await ac.post(f"/api/runs/{gid}/cancel")
            assert rc.status_code == 200
            insts = await _wait_status(
                ac, gid, lambda insts: all(i["status"] == "cancelled" for i in insts), timeout=10
            )
            assert all(i["status"] == "cancelled" for i in insts)

    asyncio.run(run())


# --- SCENARIO-105-09 -------------------------------------------------------
def test_openapi_available(tmp_path):
    async def run():
        app, _, _ = build_app(tmp_path)
        async with _client(app) as ac:
            assert (await ac.get("/openapi.json")).status_code == 200
            assert (await ac.get("/docs")).status_code == 200

    asyncio.run(run())
