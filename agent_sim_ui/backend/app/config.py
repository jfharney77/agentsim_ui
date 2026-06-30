"""Configuration for the Agent Sim UI backend (SIM-UI-100 / SIM-UI-101).

All settings are environment-overridable with sensible defaults so the backend
works out-of-the-box when run from inside the ``simulated_agentic_mesh`` repo.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _detect_repo_root() -> Path:
    """Resolve the repository root that contains ``simulators/``.

    Resolution order:
      1. ``AGENT_SIM_REPO_ROOT`` env var, if set.
      2. Walk up from this file looking for a directory containing ``simulators``.
      3. Fall back to the package's grandparent (``agent_sim_ui``'s parent).
    """
    env_root = os.getenv("AGENT_SIM_REPO_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "simulators").is_dir():
            return candidate

    # Fallback: agent_sim_ui/backend/app/config.py -> repo root is parents[3]
    return here.parents[3]


class Settings:
    """Lightweight settings object (no external deps).

    Attributes are computed at construction time from the environment so tests
    can override env vars and re-instantiate to pick up changes.
    """

    def __init__(self) -> None:
        self.repo_root: Path = _detect_repo_root()
        self.simulators_dir: Path = self.repo_root / "simulators"

        default_db = (
            Path(__file__).resolve().parents[1] / "data" / "agent_sim.db"
        )
        self.db_path: Path = Path(
            os.getenv("AGENT_SIM_DB_PATH", str(default_db))
        ).expanduser()

        cpu = os.cpu_count() or 4
        self.max_concurrency: int = int(
            os.getenv("AGENT_SIM_MAX_CONCURRENCY", str(min(32, cpu * 4)))
        )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"Settings(repo_root={self.repo_root!s}, "
            f"simulators_dir={self.simulators_dir!s}, "
            f"db_path={self.db_path!s}, max_concurrency={self.max_concurrency})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance. Call ``get_settings.cache_clear()``
    in tests after mutating the environment."""
    return Settings()
