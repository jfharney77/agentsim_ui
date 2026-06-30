"""Thin HyperAgent runner (SIM-UI-102).

Invoked as a subprocess by the launcher (``python hyperagent_runner.py [task]``)
with ``cwd`` = repo root and ``PYTHONPATH`` including the repo root. It builds a
:class:`SimulationRunner` and runs a single task, printing to stdout so the
launcher can capture output and the state tracker (SIM-UI-103) can derive agent
states.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    # repo_root is the parent that contains "simulators/".
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "simulators").is_dir():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            return


def main() -> int:
    _ensure_repo_on_path()

    task_prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.getenv("HYPERAGENT_TASK", "Fix a simple bug in a Python module.")
    )

    try:
        from simulators.hyperagent.runner import SimulationRunner
        from simulators.hyperagent.config import SimulationConfig
        from simulators.hyperagent.tasks.simulation_task import SimulationTask
    except Exception as exc:  # noqa: BLE001
        print(f"[hyperagent_runner] import error: {exc}", flush=True)
        return 1

    config = SimulationConfig.from_env()
    runner = SimulationRunner(config)
    task = SimulationTask(prompt=task_prompt)
    results = runner.run(task)

    status = (results or {}).get("planner_results", {}).get("final_status", "unknown")
    print(f"[hyperagent_runner] final_status={status}", flush=True)
    return 0 if status not in ("failed",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
