"""FastAPI backend API (SIM-UI-105).

Wires together the registry (101), launcher (102), state tracker (103), and run
store (104) into a single FastAPI app exposing REST endpoints plus an SSE event
stream. Components can be injected for testing; by default real ones are built.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from .config import Settings, get_settings
from .discovery.registry import SimulatorRegistry, SimulatorRegistryInterface
from .launcher import CompositeSink, SimulationLauncher
from .launcher.launcher import SimulationLauncherInterface
from .models import (
    InstanceDescriptor,
    LaunchRequest,
    LaunchResponse,
    RunLog,
    Simulator,
)
from .storage import RunStore
from .tracking import StateTracker
from .cv_export import export_state

logger = logging.getLogger(__name__)

# Server-side concurrency allowlist (do not trust the client). Main page offers
# {1,2,5,10}; the parallel page additionally offers {100,1000}.
ALLOWED_CONCURRENCY = {1, 2, 5, 10, 100, 1000}


def _cors_origins() -> List[str]:
    raw = os.getenv(
        "AGENT_SIM_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


class GroupSnapshot(BaseModel):
    run_group_id: str
    instances: List[InstanceDescriptor]


class CancelResponse(BaseModel):
    run_group_id: str
    status: str = "cancelled"


def create_app(
    settings: Optional[Settings] = None,
    registry: Optional[SimulatorRegistryInterface] = None,
    launcher: Optional[SimulationLauncherInterface] = None,
    tracker: Optional[StateTracker] = None,
    store: Optional[RunStore] = None,
) -> FastAPI:
    settings = settings or get_settings()
    registry = registry or SimulatorRegistry(settings=settings)
    tracker = tracker or StateTracker()
    store = store or RunStore(settings=settings)

    if launcher is None:
        sink = CompositeSink([tracker, store])
        launcher = SimulationLauncher(registry, settings=settings, sink=sink)
    # Persist each state transition (SIM-UI-104 consumes SIM-UI-103 events).
    tracker.add_listener(store.record_event)

    app = FastAPI(
        title="Agent Sim UI API",
        version="0.1.0",
        description="Discovery, launching, live agent state, and run logs for the Agent Sim UI.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.registry = registry
    app.state.launcher = launcher
    app.state.tracker = tracker
    app.state.store = store

    # -- discovery ---------------------------------------------------------
    @app.get("/api/simulators", response_model=List[Simulator])
    async def list_simulators():
        return registry.list_all()

    @app.get("/api/simulators/{simulator_id}", response_model=Simulator)
    async def get_simulator(simulator_id: str):
        sim = registry.get(simulator_id)
        if sim is None:
            raise HTTPException(status_code=404, detail=f"unknown simulator_id: {simulator_id}")
        return sim

    # -- launch ------------------------------------------------------------
    @app.post("/api/launch", response_model=LaunchResponse)
    async def launch(request: LaunchRequest):
        if registry.get(request.simulator_id) is None:
            raise HTTPException(
                status_code=404, detail=f"unknown simulator_id: {request.simulator_id}"
            )
        if request.concurrency not in ALLOWED_CONCURRENCY:
            raise HTTPException(
                status_code=400,
                detail=f"concurrency must be one of {sorted(ALLOWED_CONCURRENCY)}",
            )
        response = await launcher.launch(request)
        store.create_run_group(
            response.run_group_id,
            request.simulator_id,
            request.concurrency,
            request.task_prompt,
        )
        return response

    # -- run / instance snapshots -----------------------------------------
    @app.get("/api/runs/{run_group_id}", response_model=GroupSnapshot)
    async def get_run(run_group_id: str):
        instances = launcher.get_group(run_group_id)
        if not instances:
            raise HTTPException(status_code=404, detail=f"unknown run_group_id: {run_group_id}")
        return GroupSnapshot(run_group_id=run_group_id, instances=instances)

    @app.get("/api/instances/{instance_id}", response_model=InstanceDescriptor)
    async def get_instance(instance_id: str):
        inst = launcher.get_instance(instance_id)
        if inst is None:
            raise HTTPException(status_code=404, detail=f"unknown instance_id: {instance_id}")
        return inst

    @app.get("/api/instances/{instance_id}/log", response_model=RunLog)
    async def get_instance_log(instance_id: str):
        return store.get_run_log(instance_id)

    @app.get("/api/instances/{instance_id}/summary")
    async def get_instance_summary(instance_id: str):
        summary = store.get_instance_summary(instance_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"no summary for instance_id: {instance_id}")
        return summary

    @app.post("/api/runs/{run_group_id}/cancel", response_model=CancelResponse)
    async def cancel_run(run_group_id: str):
        if not launcher.get_group(run_group_id):
            raise HTTPException(status_code=404, detail=f"unknown run_group_id: {run_group_id}")
        await launcher.cancel(run_group_id)
        return CancelResponse(run_group_id=run_group_id)

    # -- context window export (SIM-UI-109) ---------------------------------
    @app.get("/api/instances/{instance_id}/agents/{agent_id}/context")
    async def get_agent_context(instance_id: str, agent_id: str):
        """Export agent context as Context Visualizer-compatible state.json.

        Returns a placeholder state for now. Full context capture requires
        instrumenting simulators to capture LLM prompts/messages during runs.
        """
        # Placeholder: return empty state with required schema
        state = export_state(
            messages=[],
            model="unknown",
            context_window_tokens=128_000,
            tools=[],
            timestamp=None,
        )
        return state

    # -- streaming ---------------------------------------------------------
    @app.get("/api/runs/{run_group_id}/events")
    async def stream_events(run_group_id: str):
        async def event_generator():
            async for event in tracker.subscribe(run_group_id):
                yield f"data: {event.model_dump_json()}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return app
