"""RunStore — durable run logging in SQLite (SIM-UI-104).

Persists run groups, instances, every captured log line, every agent state
transition, and a per-instance performance summary to a single SQLite file
(``AGENT_SIM_DB_PATH``). Opened in WAL mode; log-line writes are buffered and
flushed in batches so high-volume output never blocks instance execution.

The store doubles as a :class:`LaunchSink` (consuming log lines + lifecycle from
SIM-UI-102) and a state-event listener (consuming transitions from SIM-UI-103),
but every capability is also exposed through :class:`RunStoreInterface` so it
can be driven directly and swapped for another backend later.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..config import Settings, get_settings
from ..launcher.sinks import LaunchSink
from ..models import (
    AgentRuntimeState,
    AgentState,
    InstanceDescriptor,
    InstanceStatus,
    LogLine,
    RunLog,
    StateChangeEvent,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_group (
    run_group_id TEXT PRIMARY KEY,
    simulator_id TEXT,
    concurrency  INTEGER,
    created_at   TEXT,
    task_prompt  TEXT
);
CREATE TABLE IF NOT EXISTS instance (
    instance_id  TEXT PRIMARY KEY,
    run_group_id TEXT,
    simulator_id TEXT,
    idx          INTEGER,
    status       TEXT,
    started_at   TEXT,
    ended_at     TEXT,
    return_code  INTEGER
);
CREATE TABLE IF NOT EXISTS log_line (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT,
    seq         INTEGER,
    ts          TEXT,
    agent_id    TEXT,
    level       TEXT,
    message     TEXT
);
CREATE TABLE IF NOT EXISTS agent_event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id   TEXT,
    agent_id      TEXT,
    agent_name    TEXT,
    old_state     TEXT,
    new_state     TEXT,
    ts            TEXT,
    failure_modes TEXT
);
CREATE TABLE IF NOT EXISTS instance_summary (
    instance_id  TEXT PRIMARY KEY,
    summary_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_log_instance_seq ON log_line(instance_id, seq);
CREATE INDEX IF NOT EXISTS idx_event_instance ON agent_event(instance_id);
CREATE INDEX IF NOT EXISTS idx_instance_group ON instance(run_group_id);
"""


class RunStoreInterface:
    def create_run_group(self, run_group_id, simulator_id, concurrency, task_prompt=None): ...
    def create_instance(self, instance_id, run_group_id, simulator_id, idx, status): ...
    def append_log(self, instance_id: str, line: LogLine) -> None: ...
    def record_event(self, event: StateChangeEvent) -> None: ...
    def finalize_instance(self, instance_id, status, return_code, agents=None): ...
    def get_run_log(self, instance_id: str) -> RunLog: ...
    def get_instance_summary(self, instance_id: str) -> Optional[dict]: ...
    def list_runs(self, filters: Optional[dict] = None) -> List[dict]: ...


class RunStore(RunStoreInterface, LaunchSink):
    def __init__(
        self,
        settings: Optional[Settings] = None,
        db_path: Optional[Path] = None,
        batch_size: int = 200,
    ) -> None:
        self._settings = settings or get_settings()
        self._db_path = Path(db_path) if db_path else self._settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._batch_size = batch_size

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.executescript(_SCHEMA)

        self._seq: Dict[str, int] = {}
        self._log_buffer: List[tuple] = []

    # -- RunStoreInterface: writes -----------------------------------------
    def create_run_group(self, run_group_id, simulator_id, concurrency, task_prompt=None):
        with self._lock:
            self._conn.execute(
                """INSERT INTO run_group(run_group_id, simulator_id, concurrency, created_at, task_prompt)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(run_group_id) DO UPDATE SET
                       simulator_id=excluded.simulator_id,
                       concurrency=excluded.concurrency,
                       task_prompt=excluded.task_prompt""",
                (run_group_id, simulator_id, concurrency, _now_iso(), task_prompt),
            )

    def _ensure_run_group(self, run_group_id, simulator_id):
        self._conn.execute(
            """INSERT OR IGNORE INTO run_group(run_group_id, simulator_id, concurrency, created_at, task_prompt)
               VALUES(?,?,?,?,?)""",
            (run_group_id, simulator_id, None, _now_iso(), None),
        )

    def create_instance(self, instance_id, run_group_id, simulator_id, idx, status):
        status = status.value if isinstance(status, InstanceStatus) else status
        with self._lock:
            self._ensure_run_group(run_group_id, simulator_id)
            self._conn.execute(
                """INSERT OR IGNORE INTO instance(instance_id, run_group_id, simulator_id, idx, status, started_at, ended_at, return_code)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (instance_id, run_group_id, simulator_id, idx, status, _now_iso(), None, None),
            )

    def append_log(self, instance_id: str, line: LogLine) -> None:
        with self._lock:
            seq = self._seq.get(instance_id, 0)
            self._seq[instance_id] = seq + 1
            ts = _iso(line.ts) or _now_iso()
            self._log_buffer.append(
                (instance_id, seq, ts, line.agent_id, line.level, line.message)
            )
            if len(self._log_buffer) >= self._batch_size:
                self._flush_locked()

    def record_event(self, event: StateChangeEvent) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO agent_event(instance_id, agent_id, agent_name, old_state, new_state, ts, failure_modes)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    event.instance_id,
                    event.agent_id,
                    event.agent_name,
                    event.old_state.value,
                    event.new_state.value,
                    _iso(event.ts) or _now_iso(),
                    json.dumps(event.failure_modes),
                ),
            )

    def finalize_instance(
        self,
        instance_id: str,
        status,
        return_code: Optional[int],
        agents: Optional[List[AgentRuntimeState]] = None,
    ) -> None:
        status = status.value if isinstance(status, InstanceStatus) else status
        self.flush()
        summary = self._build_summary(instance_id, status, return_code, agents)
        with self._lock:
            self._conn.execute(
                "UPDATE instance SET status=?, ended_at=?, return_code=? WHERE instance_id=?",
                (status, _now_iso(), return_code, instance_id),
            )
            self._conn.execute(
                """INSERT INTO instance_summary(instance_id, summary_json) VALUES(?,?)
                   ON CONFLICT(instance_id) DO UPDATE SET summary_json=excluded.summary_json""",
                (instance_id, json.dumps(summary)),
            )

    # -- LaunchSink hooks --------------------------------------------------
    async def on_instance_created(self, instance: InstanceDescriptor) -> None:
        self.create_instance(
            instance.instance_id,
            instance.run_group_id,
            instance.simulator_id,
            instance.index,
            instance.status,
        )

    async def on_log_line(self, instance_id: str, line: str) -> None:
        self.append_log(
            instance_id,
            LogLine(ts=datetime.now(timezone.utc), agent_id=None, level="INFO", message=line),
        )

    async def on_instance_exit(self, instance_id: str, return_code: int, status: InstanceStatus) -> None:
        self.finalize_instance(instance_id, status, return_code)

    # -- RunStoreInterface: reads ------------------------------------------
    def get_run_log(self, instance_id: str) -> RunLog:
        self.flush()
        with self._lock:
            inst = self._conn.execute(
                "SELECT simulator_id, started_at FROM instance WHERE instance_id=?",
                (instance_id,),
            ).fetchone()
            rows = self._conn.execute(
                "SELECT ts, agent_id, level, message FROM log_line WHERE instance_id=? ORDER BY seq ASC",
                (instance_id,),
            ).fetchall()
        lines = [
            LogLine(
                ts=_parse_dt(r["ts"]),
                agent_id=r["agent_id"],
                level=r["level"] or "INFO",
                message=r["message"] or "",
            )
            for r in rows
        ]
        return RunLog(
            instance_id=instance_id,
            simulator_id=(inst["simulator_id"] if inst else "") or "",
            created_at=_parse_dt(inst["started_at"]) if inst and inst["started_at"] else datetime.now(timezone.utc),
            lines=lines,
        )

    def get_instance_summary(self, instance_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT summary_json FROM instance_summary WHERE instance_id=?",
                (instance_id,),
            ).fetchone()
        if row and row["summary_json"]:
            return json.loads(row["summary_json"])
        # Fall back to reconstructing from events if not yet finalized.
        return self._build_summary(instance_id, None, None, None)

    def list_runs(self, filters: Optional[dict] = None) -> List[dict]:
        filters = filters or {}
        clause, params = "", []
        if filters.get("simulator_id"):
            clause = " WHERE simulator_id=?"
            params.append(filters["simulator_id"])
        with self._lock:
            groups = self._conn.execute(
                f"SELECT * FROM run_group{clause} ORDER BY created_at DESC", params
            ).fetchall()
            result = []
            for g in groups:
                insts = self._conn.execute(
                    "SELECT instance_id, idx, status, return_code FROM instance WHERE run_group_id=? ORDER BY idx",
                    (g["run_group_id"],),
                ).fetchall()
                result.append(
                    {
                        "run_group_id": g["run_group_id"],
                        "simulator_id": g["simulator_id"],
                        "concurrency": g["concurrency"],
                        "created_at": g["created_at"],
                        "task_prompt": g["task_prompt"],
                        "instances": [dict(i) for i in insts],
                    }
                )
        return result

    # -- maintenance -------------------------------------------------------
    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._log_buffer:
            return
        self._conn.executemany(
            "INSERT INTO log_line(instance_id, seq, ts, agent_id, level, message) VALUES(?,?,?,?,?,?)",
            self._log_buffer,
        )
        self._log_buffer.clear()

    def close(self) -> None:
        self.flush()
        with self._lock:
            self._conn.close()

    # -- internals ---------------------------------------------------------
    def _build_summary(
        self,
        instance_id: str,
        status: Optional[str],
        return_code: Optional[int],
        agents: Optional[List[AgentRuntimeState]],
    ) -> dict:
        agent_summaries: List[dict] = []
        if agents is not None:
            for a in agents:
                agent_summaries.append(self._agent_summary_dict(
                    a.agent_id, a.agent_name, a.state.value,
                    _iso(a.started_at), _iso(a.ended_at), a.failure_modes,
                ))
        else:
            # Reconstruct from agent_event rows.
            with self._lock:
                rows = self._conn.execute(
                    "SELECT agent_id, agent_name, new_state, ts, failure_modes FROM agent_event WHERE instance_id=? ORDER BY id",
                    (instance_id,),
                ).fetchall()
            by_agent: Dict[str, dict] = {}
            for r in rows:
                rec = by_agent.setdefault(
                    r["agent_id"],
                    {"agent_name": r["agent_name"], "final_state": "not_started",
                     "started_at": None, "ended_at": None, "failure_modes": []},
                )
                rec["final_state"] = r["new_state"]
                if r["new_state"] == AgentState.RUNNING.value and rec["started_at"] is None:
                    rec["started_at"] = r["ts"]
                if r["new_state"] in (AgentState.COMPLETED.value, AgentState.ERRORED.value):
                    rec["ended_at"] = r["ts"]
                try:
                    fms = json.loads(r["failure_modes"] or "[]")
                except json.JSONDecodeError:
                    fms = []
                for fm in fms:
                    if fm not in rec["failure_modes"]:
                        rec["failure_modes"].append(fm)
            for agent_id, rec in by_agent.items():
                agent_summaries.append(self._agent_summary_dict(
                    agent_id, rec["agent_name"], rec["final_state"],
                    rec["started_at"], rec["ended_at"], rec["failure_modes"],
                ))

        starts = [a["started_at"] for a in agent_summaries if a["started_at"]]
        ends = [a["ended_at"] for a in agent_summaries if a["ended_at"]]
        return {
            "instance_id": instance_id,
            "status": status,
            "return_code": return_code,
            "started_at": min(starts) if starts else None,
            "ended_at": max(ends) if ends else None,
            "agents": agent_summaries,
        }

    @staticmethod
    def _agent_summary_dict(agent_id, agent_name, final_state, started_at, ended_at, failure_modes):
        duration = None
        if started_at and ended_at:
            try:
                duration = (_parse_dt(ended_at) - _parse_dt(started_at)).total_seconds()
            except Exception:  # noqa: BLE001
                duration = None
        return {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "final_state": final_state,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration,
            "failure_modes": list(failure_modes or []),
        }


def _parse_dt(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
