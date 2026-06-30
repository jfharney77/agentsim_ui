"""ASGI entrypoint for the Agent Sim UI backend (SIM-UI-105).

Run with:

    uvicorn app.main:app --reload --port 8000   # from agent_sim_ui/backend
"""

from __future__ import annotations

from .api import create_app

app = create_app()
