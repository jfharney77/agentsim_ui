"""Launch sinks (SIM-UI-102).

The launcher forwards lifecycle and output events to one or more *sinks*.
SIM-UI-103 (state tracking) and SIM-UI-104 (logging) implement sinks to consume
captured output and process lifecycle events. All hooks are async and default
to no-ops so sinks only override what they need.
"""

from __future__ import annotations

from typing import List

from ..models import InstanceDescriptor, InstanceStatus


class LaunchSink:
    """Base class for launcher event consumers (all hooks optional)."""

    async def on_instance_created(self, instance: InstanceDescriptor) -> None:
        """Called once per instance at launch time (status PENDING)."""

    async def on_instance_start(self, instance: InstanceDescriptor) -> None:
        """Called when an instance's main process has been spawned (RUNNING)."""

    async def on_log_line(self, instance_id: str, line: str) -> None:
        """Called for every captured stdout/stderr line of an instance."""

    async def on_status_change(
        self, instance_id: str, status: InstanceStatus
    ) -> None:
        """Called whenever an instance's status changes."""

    async def on_instance_exit(
        self, instance_id: str, return_code: int, status: InstanceStatus
    ) -> None:
        """Called when an instance's process has exited and been finalized."""


class CompositeSink(LaunchSink):
    """Fan a single event out to multiple sinks, isolating failures."""

    def __init__(self, sinks: List[LaunchSink] | None = None) -> None:
        self._sinks: List[LaunchSink] = list(sinks or [])

    def add(self, sink: LaunchSink) -> None:
        self._sinks.append(sink)

    async def on_instance_created(self, instance: InstanceDescriptor) -> None:
        for s in self._sinks:
            await _safe(s.on_instance_created(instance))

    async def on_instance_start(self, instance: InstanceDescriptor) -> None:
        for s in self._sinks:
            await _safe(s.on_instance_start(instance))

    async def on_log_line(self, instance_id: str, line: str) -> None:
        for s in self._sinks:
            await _safe(s.on_log_line(instance_id, line))

    async def on_status_change(
        self, instance_id: str, status: InstanceStatus
    ) -> None:
        for s in self._sinks:
            await _safe(s.on_status_change(instance_id, status))

    async def on_instance_exit(
        self, instance_id: str, return_code: int, status: InstanceStatus
    ) -> None:
        for s in self._sinks:
            await _safe(s.on_instance_exit(instance_id, return_code, status))


async def _safe(coro) -> None:
    """Await a sink coroutine, swallowing exceptions so one bad sink cannot
    break the launcher or the other sinks."""
    try:
        await coro
    except Exception:  # noqa: BLE001 - sinks must never break the launcher
        import logging

        logging.getLogger(__name__).exception("sink hook failed")
