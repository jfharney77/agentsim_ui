from __future__ import annotations

import os

HOST = "127.0.0.1"
BASE_PORT = int(os.getenv("PORT_BASE", "9001"))

_ROLE_OFFSETS = {
    "researcher": 0,
    "analyst": 1,
    "writer": 2,
}


def port_for(role: str) -> int:
    return BASE_PORT + _ROLE_OFFSETS[role]


def host_port(role: str) -> tuple[str, int]:
    return HOST, port_for(role)


def base_url(role: str) -> str:
    return f"http://{HOST}:{port_for(role)}"
