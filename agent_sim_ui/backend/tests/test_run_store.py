"""Tests for SIM-UI-104 Run Logging & SQLite Persistence.

Covers SCENARIO-104-01 .. SCENARIO-104-07.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.models import (
    AgentRuntimeState,
    AgentState,
    InstanceStatus,
    LogLine,
    StateChangeEvent,
)
from app.storage import RunStore


def _store(tmp_path, batch_size=200) -> RunStore:
    return RunStore(settings=Settings(), db_path=tmp_path / "test.db", batch_size=batch_size)


def _log(msg: str) -> LogLine:
    return LogLine(ts=datetime.now(timezone.utc), level="INFO", message=msg)


def _event(instance_id, agent_id, agent_name, old, new, fms=None) -> StateChangeEvent:
    return StateChangeEvent(
        instance_id=instance_id, run_group_id="g1", agent_id=agent_id,
        agent_name=agent_name, old_state=old, new_state=new,
        ts=datetime.now(timezone.utc), failure_modes=fms or [],
    )


# --- SCENARIO-104-01 -------------------------------------------------------
def test_unique_ids_persisted(tmp_path):
    store = _store(tmp_path)
    store.create_run_group("g1", "chatdev", concurrency=3)
    for i in range(3):
        store.create_instance(f"i{i}", "g1", "chatdev", i, InstanceStatus.RUNNING)
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_group_id"] == "g1"
    ids = {inst["instance_id"] for inst in runs[0]["instances"]}
    assert ids == {"i0", "i1", "i2"}


# --- SCENARIO-104-02 -------------------------------------------------------
def test_log_lines_stored_in_order(tmp_path):
    store = _store(tmp_path, batch_size=3)
    store.create_instance("i0", "g1", "chatdev", 0, InstanceStatus.RUNNING)
    messages = [f"line {n}" for n in range(10)]
    for m in messages:
        store.append_log("i0", _log(m))
    log = store.get_run_log("i0")
    assert [ln.message for ln in log.lines] == messages


# --- SCENARIO-104-03 -------------------------------------------------------
def test_agent_events_recorded(tmp_path):
    store = _store(tmp_path)
    store.create_instance("i0", "g1", "chatdev", 0, InstanceStatus.RUNNING)
    store.record_event(_event("i0", "programmer", "Programmer", AgentState.NOT_STARTED, AgentState.RUNNING))
    store.record_event(_event("i0", "programmer", "Programmer", AgentState.RUNNING, AgentState.COMPLETED))
    summary = store.get_instance_summary("i0")
    prog = next(a for a in summary["agents"] if a["agent_id"] == "programmer")
    assert prog["final_state"] == "completed"
    assert prog["started_at"] is not None and prog["ended_at"] is not None


# --- SCENARIO-104-04 -------------------------------------------------------
def test_errored_agent_in_summary(tmp_path):
    store = _store(tmp_path)
    store.create_instance("i0", "g1", "metagpt", 0, InstanceStatus.RUNNING)
    agents = [
        AgentRuntimeState(
            agent_id="architect", agent_name="Architect", state=AgentState.ERRORED,
            started_at=datetime.now(timezone.utc), ended_at=datetime.now(timezone.utc),
            failure_modes=["FM-2.4"],
        ),
        AgentRuntimeState(agent_id="engineer", agent_name="Engineer", state=AgentState.NOT_STARTED),
    ]
    store.finalize_instance("i0", InstanceStatus.FAILED, return_code=1, agents=agents)
    summary = store.get_instance_summary("i0")
    arch = next(a for a in summary["agents"] if a["agent_id"] == "architect")
    assert arch["final_state"] == "errored"
    assert "FM-2.4" in arch["failure_modes"]
    assert summary["status"] == "failed"
    assert summary["return_code"] == 1


# --- SCENARIO-104-05 -------------------------------------------------------
def test_survives_restart(tmp_path):
    db = tmp_path / "persist.db"
    store = RunStore(settings=Settings(), db_path=db)
    store.create_instance("i0", "g1", "chatdev", 0, InstanceStatus.RUNNING)
    for n in range(5):
        store.append_log("i0", _log(f"line {n}"))
    store.finalize_instance("i0", InstanceStatus.COMPLETED, return_code=0, agents=[])
    store.close()

    # New process/store instance pointing at the same DB file.
    store2 = RunStore(settings=Settings(), db_path=db)
    log = store2.get_run_log("i0")
    assert [ln.message for ln in log.lines] == [f"line {n}" for n in range(5)]


# --- SCENARIO-104-06 -------------------------------------------------------
def test_retrieval_by_instance_no_cross_contamination(tmp_path):
    store = _store(tmp_path)
    store.create_instance("iA", "g1", "chatdev", 0, InstanceStatus.RUNNING)
    store.create_instance("iB", "g1", "chatdev", 1, InstanceStatus.RUNNING)
    store.append_log("iA", _log("A-1"))
    store.append_log("iB", _log("B-1"))
    store.append_log("iA", _log("A-2"))
    a_lines = [ln.message for ln in store.get_run_log("iA").lines]
    b_lines = [ln.message for ln in store.get_run_log("iB").lines]
    assert a_lines == ["A-1", "A-2"]
    assert b_lines == ["B-1"]


# --- SCENARIO-104-07 -------------------------------------------------------
def test_non_blocking_under_load(tmp_path):
    store = _store(tmp_path, batch_size=100)
    n_instances, n_lines = 50, 50
    for i in range(n_instances):
        store.create_instance(f"i{i}", "g1", "chatdev", i, InstanceStatus.RUNNING)

    start = time.monotonic()
    for line_no in range(n_lines):
        for i in range(n_instances):
            store.append_log(f"i{i}", _log(f"line {line_no}"))
    elapsed = time.monotonic() - start
    # 2500 buffered appends must be fast (batched, not per-line fsync).
    assert elapsed < 2.0, f"appends too slow: {elapsed:.2f}s"

    store.flush()
    # ordering preserved per instance
    log = store.get_run_log("i7")
    assert [ln.message for ln in log.lines] == [f"line {n}" for n in range(n_lines)]
