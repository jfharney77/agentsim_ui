"""Export a LangGraph/agent run's message history as a Context Visualizer
``state.json``.

Two entry points:

- :func:`export_state` — write a complete snapshot in one shot (what you'd call
  at the end of a run, or whenever you just want a static file to inspect).
- :func:`export_state_incremental` — append message(s) to an existing
  ``state.json`` and rewrite it **atomically**, intended to be called once per
  new message during a *live* run. The backend's ``GET /api/watch/stream``
  endpoint polls the file and pushes each update to the Live Monitor tab, so the
  context window animates in real time as the agent works.

Both write atomically (temp file in the same directory + ``os.replace``) so a
reader never sees a half-written file — important for the live watcher, which
may poll mid-write.

Messages may be plain dicts already in the schema (``role``/``content``/
``tool_calls``/``tool_name``) or LangChain message objects (``SystemMessage``,
``HumanMessage``, ``AIMessage``, ``ToolMessage``); :func:`message_to_dict`
normalizes either form.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# LangChain role -> the role strings the visualizer's `categorize()` expects.
_LC_TYPE_TO_ROLE = {
    "system": "system",
    "human": "human",
    "ai": "ai",
    "tool": "tool",
    "function": "tool",
}


def message_to_dict(msg: Any) -> dict:
    """Normalize one message (dict or LangChain message object) to the schema.

    A dict is passed through (defensively copied); anything else is treated as a
    LangChain-style message and read via its ``type``/``content``/
    ``tool_calls``/``name`` attributes.
    """
    if isinstance(msg, dict):
        return dict(msg)

    role = _LC_TYPE_TO_ROLE.get(getattr(msg, "type", None), getattr(msg, "type", None))
    out: dict[str, Any] = {"role": role, "content": getattr(msg, "content", "") or ""}

    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        # LangChain tool calls are dicts with name/args/id; keep name + args, the
        # two fields the visualizer renders and tokenizes.
        out["tool_calls"] = [
            {"name": tc.get("name", ""), "args": tc.get("args", {})}
            for tc in tool_calls
        ]
    # ToolMessage carries the originating tool's name; surface it as tool_name.
    name = getattr(msg, "name", None)
    if role == "tool" and name:
        out["tool_name"] = name
    return out


def _normalize_messages(messages: Iterable[Any]) -> list[dict]:
    return [message_to_dict(m) for m in messages]


def _atomic_write_json(path: Path, obj: dict) -> None:
    """Write ``obj`` as JSON to ``path`` atomically.

    Writes to a temp file in the same directory (so ``os.replace`` is a same-
    filesystem rename) and replaces the target in one step. Readers therefore
    only ever see the old file or the fully-written new one — never a partial.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # Don't leave a stray temp file behind on failure.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _build_state(
    messages: list[dict],
    *,
    model: str,
    context_window_tokens: int,
    tools: list[str] | None,
    timestamp: str | None,
) -> dict:
    return {
        "model": model,
        "context_window_tokens": context_window_tokens,
        "timestamp": timestamp or datetime.now().isoformat(timespec="seconds"),
        "tools": list(tools or []),
        "messages": messages,
    }


def export_state(
    messages: Iterable[Any],
    path: str | os.PathLike = "state.json",
    *,
    model: str = "unknown",
    context_window_tokens: int = 128_000,
    tools: list[str] | None = None,
    timestamp: str | None = None,
) -> dict:
    """Write a complete ``state.json`` snapshot, atomically. Returns the dict."""
    state = _build_state(
        _normalize_messages(messages),
        model=model,
        context_window_tokens=context_window_tokens,
        tools=tools,
        timestamp=timestamp,
    )
    _atomic_write_json(Path(path), state)
    return state


def export_state_incremental(
    new_messages: Any | Iterable[Any],
    path: str | os.PathLike = "state.json",
    *,
    model: str | None = None,
    context_window_tokens: int | None = None,
    tools: list[str] | None = None,
    timestamp: str | None = None,
) -> dict:
    """Append message(s) to an existing ``state.json`` and rewrite it atomically.

    Call this once per new message during a live run (e.g. from a LangGraph node
    or an ``on_message`` hook) so the Live Monitor watcher sees the window grow
    in real time. ``new_messages`` may be a single message or an iterable of
    them, each a dict or a LangChain message object.

    Metadata (``model``, ``context_window_tokens``, ``tools``) is only written
    when provided — typically on the first call, then omitted on subsequent
    appends. If the file doesn't exist yet it's created with sensible defaults
    (``model="unknown"``, 128k window). The ``timestamp`` is refreshed on every
    write so the UI can show "last updated". Returns the full state dict written.
    """
    path = Path(path)
    if path.exists():
        try:
            state = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            state = {}
    else:
        state = {}
    if not isinstance(state, dict):
        state = {}

    state.setdefault("messages", [])
    state.setdefault("model", model if model is not None else "unknown")
    state.setdefault(
        "context_window_tokens",
        context_window_tokens if context_window_tokens is not None else 128_000,
    )
    state.setdefault("tools", list(tools or []))

    # Allow callers to update metadata on any call (e.g. window size discovered
    # later); only overwrite when an explicit value is passed.
    if model is not None:
        state["model"] = model
    if context_window_tokens is not None:
        state["context_window_tokens"] = context_window_tokens
    if tools is not None:
        state["tools"] = list(tools)

    # Accept a single message or an iterable; a dict is itself iterable so guard
    # against treating one message as a list of its keys.
    if isinstance(new_messages, dict) or not isinstance(new_messages, Iterable):
        batch: Iterable[Any] = [new_messages]
    else:
        batch = new_messages
    state["messages"].extend(_normalize_messages(batch))
    state["timestamp"] = timestamp or datetime.now().isoformat(timespec="seconds")

    _atomic_write_json(path, state)
    return state


if __name__ == "__main__":
    # Demo: simulate a live run that grows a state.json one message at a time, so
    # you can point the Live Monitor at it and watch the bar fill.
    #   python cv_export.py [out_path] [delay_seconds]
    import sys
    import time

    out = sys.argv[1] if len(sys.argv) > 1 else "live_state.json"
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    export_state([], out, model="qwen2.5", context_window_tokens=32_768,
                 tools=["web_search", "calculator"])
    script = [
        {"role": "system", "content": "You are a helpful research assistant. " * 8},
        {"role": "human", "content": "Summarize the latest on small modular reactors. " * 4},
        {"role": "ai", "content": "Let me search for current information.",
         "tool_calls": [{"name": "web_search", "args": {"query": "SMR status 2026"}}]},
        {"role": "tool", "tool_name": "web_search", "content": "Results: " + ("finding. " * 60)},
        {"role": "ai", "content": "Based on the findings, here is a brief report. " * 20},
    ]
    for m in script:
        export_state_incremental(m, out)
        print(f"appended {m['role']} -> {out}")
        time.sleep(delay)
    print("done")
