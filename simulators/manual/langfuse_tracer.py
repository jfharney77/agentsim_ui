"""Optional Langfuse tracing for manual simulator agents.

Activates automatically when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are
set in the environment. Silent no-op otherwise — agents run normally without
any Langfuse configuration.

Langfuse SDK version: 4.10.0

API surface used:
  get_client()                        -- singleton Langfuse client
  lf.start_as_current_observation(...) -- create root span observation
  span.start_as_current_generation(...) -- child generation observation
  lf.create_score(...)                -- attach numeric score to a trace
  lf.flush()                          -- drain event queue at process exit

Scores recorded for degrading agents (queryable by downstream analysis):
  degradation_level     0.0 (healthy) → 1.0 (fully degraded)
  call_severity         MAST severity score for this single call
  cumulative_severity   Running lifetime severity total across all calls
  active_failure_count  Number of MAST failure modes fired this call
  is_terminal           1.0 if agent has been decommissioned, else 0.0
"""

from __future__ import annotations

import os
import re
import uuid

_lf = None
_enabled: bool | None = None
_session_id: str | None = None
_SESSION_PREFIX = "__LF_SESSION_ID__:"


def _client():
    """Lazy-init the Langfuse singleton; returns None if not configured."""
    global _lf, _enabled, _session_id
    if _enabled is None:
        _enabled = bool(
            os.environ.get("LANGFUSE_PUBLIC_KEY")
            and os.environ.get("LANGFUSE_SECRET_KEY")
        )
        if not _enabled:
            print(
                "[Langfuse] Tracing disabled. Set LANGFUSE_PUBLIC_KEY and "
                "LANGFUSE_SECRET_KEY to enable."
            )
        if _enabled:
            try:
                from langfuse import get_client

                _lf = get_client()
                _session_id = os.environ.get("LANGFUSE_SESSION_ID") or str(uuid.uuid4())
                print(f"[Langfuse] Tracing enabled. session_id={_session_id}")
            except Exception as exc:
                print(f"[Langfuse] Init failed — tracing disabled: {exc}")
                _enabled = False
    return _lf if _enabled else None


def get_session_id() -> str | None:
    """Return the current session ID (None if Langfuse is not configured)."""
    _client()
    return _session_id


def inject_session_id(text: str, session_id: str | None) -> str:
    """Encode a run-level session id into message text for transport over A2A."""
    if not session_id:
        return text
    return f"{_SESSION_PREFIX}{session_id}\n{text}"


def extract_session_id(text: str) -> tuple[str, str | None]:
    """Decode optional run-level session id from message text.

    Returns (clean_text, session_id). If no marker is present, session_id is None.
    """
    if not text.startswith(_SESSION_PREFIX):
        return text, None

    encoded = text[len(_SESSION_PREFIX) :]
    first_line, sep, remainder = encoded.partition("\n")

    if sep:
        session_id = first_line.strip() or None
        if remainder:
            print(
                f"[DEBUG extract_session_id] session={session_id}, text_len={len(remainder)}, text_preview={remainder[:60]!r}"
            )
            return remainder, session_id
        print(
            f"[DEBUG extract_session_id] session={session_id}, NO REMAINDER, returning original text"
        )
        return text, session_id

    # Fallback: handle payloads where transport normalized away separators.
    # Supports either "<session-id> <original-text>" or
    # "<session-id><original-text>" (UUID session IDs from run scripts).
    session_and_text = first_line.strip()
    if not session_and_text:
        return text, None

    session_parts = session_and_text.split(maxsplit=1)
    if len(session_parts) > 1:
        session_id = session_parts[0].strip() or None
        clean_text = session_parts[1]
        if clean_text:
            return clean_text, session_id
        return text, session_id

    uuid_match = re.match(
        r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(.*)$",
        session_and_text,
    )
    if uuid_match:
        session_id = uuid_match.group(1)
        clean_text = uuid_match.group(2).lstrip()
        if clean_text:
            return clean_text, session_id
        return text, session_id

    # Unknown marker shape: keep payload untouched to avoid blank traces.
    return text, None


def _create_trace_score(
    *,
    lf,
    trace_id: str | None,
    name: str,
    value: float,
    comment: str,
    data_type: str = "NUMERIC",
) -> None:
    if not trace_id:
        return
    try:
        lf.create_score(
            trace_id=trace_id,
            name=name,
            value=value,
            data_type=data_type,
            comment=comment,
        )
    except Exception as exc:
        print(f"[Langfuse] create_score failed for '{name}': {exc}")


def trace_standard_agent(
    *,
    agent_name: str,
    topology: str,
    model: str,
    system_prompt: str,
    user_input: str,
    output: str,
    session_id: str | None = None,
) -> None:
    """Trace one non-degrading agent turn (researcher, writer).

    Creates a root trace with a single generation child observation.
    Uses the module-level session_id to group traces from the same server run.

    Args:
        agent_name: Role label, e.g. "researcher", "writer".
        topology:   "swarm" or "orchestrator".
        model:      Model identifier string (e.g. "claude-sonnet-4-5-20250929").
        system_prompt: Agent's system prompt.
        user_input: Text received from the calling peer or hub.
        output:     Text the agent returned.
    """
    lf = _client()
    if lf is None:
        return
    effective_session_id = session_id or _session_id
    trace_name = f"{topology}-{agent_name}"
    print(
        f"[DEBUG trace_standard_agent] Creating trace: name={trace_name!r}, session_id={effective_session_id}, input_len={len(user_input)}, output_len={len(output)}"
    )
    try:
        from langfuse import propagate_attributes

        with propagate_attributes(session_id=effective_session_id):
            with lf.start_as_current_observation(
                as_type="span",
                name=trace_name,
                input={"user_input": user_input},
                output={"text": output},
                metadata={
                    "topology": topology,
                    "agent": agent_name,
                    "model": model,
                },
            ) as obs:
                with lf.start_as_current_observation(
                    as_type="generation",
                    name="llm-generation",
                    model=model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                ) as generation:
                    generation.update(output=output)
        print(f"[DEBUG trace_standard_agent] Trace submitted successfully")
    except Exception as exc:
        print(f"[Langfuse] trace_standard_agent failed: {exc}")


def trace_degrading_agent(
    *,
    agent_name: str,
    topology: str,
    model: str,
    system_prompt: str,
    user_input: str,
    output: str,
    state,
    session_id: str | None = None,
) -> None:
    """Trace one degrading agent turn with MAST degradation scores.

    Creates a root trace tagged with every active MAST failure mode code,
    a generation child, and five numeric scores designed for downstream
    analysis of the agent's degradation arc.

    Args:
        agent_name: Role label, e.g. "analyst".
        topology:   "swarm" or "orchestrator".
        model:      Model identifier string.
        system_prompt: Agent's system prompt.
        user_input: Text received (original, before FM-1.4 mutation).
        output:     Text returned (includes failure-mode prefix strings).
        state:      DegradationState instance after this call has advanced.
    """
    lf = _client()
    if lf is None:
        return
    effective_session_id = session_id or _session_id
    try:
        tags = [
            f"agent:{agent_name}",
            f"topology:{topology}",
            "degrading",
        ] + state.active_failures
        if state.is_terminal:
            tags.append("terminal")
        if state.degradation_level >= 0.8:
            tags.append("critical-zone")

        metadata = {
            "topology": topology,
            "agent": agent_name,
            "model": model,
            "call_count": state.call_count,
            "degradation_level": state.degradation_level,
            "active_failures": state.active_failures,
            "total_severity": state.total_severity,
            "cumulative_severity": state.cumulative_severity,
            "cycles_in_critical": state.cycles_in_critical,
            "is_terminal": state.is_terminal,
            "terminal_reason": state.terminal_reason if state.is_terminal else None,
        }

        from langfuse import propagate_attributes

        trace_name = f"{topology}-{agent_name}-degrading-call-{state.call_count}"
        with propagate_attributes(session_id=effective_session_id):
            with lf.start_as_current_observation(
                as_type="span",
                name=trace_name,
                input={"system_prompt": system_prompt, "user_input": user_input},
                output={"text": output},
                metadata=metadata,
            ) as obs:
                with lf.start_as_current_observation(
                    as_type="generation",
                    name="llm-generation",
                    model=model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                    metadata={"active_failures": state.active_failures},
                ) as generation:
                    generation.update(output=output)

        # Get trace_id from the observation context for scoring
        trace_id = getattr(obs, "trace_id", None)
        _create_trace_score(
            lf=lf,
            trace_id=trace_id,
            name="degradation_level",
            value=state.degradation_level,
            comment=f"Call {state.call_count}: 0.0=healthy, 1.0=fully degraded",
        )
        _create_trace_score(
            lf=lf,
            trace_id=trace_id,
            name="call_severity",
            value=state.total_severity,
            comment=(
                f"MAST severity for call {state.call_count}. "
                f"Failures: {', '.join(state.active_failures) if state.active_failures else 'none'}"
            ),
        )
        _create_trace_score(
            lf=lf,
            trace_id=trace_id,
            name="cumulative_severity",
            value=state.cumulative_severity,
            comment=f"Lifetime MAST severity after {state.call_count} calls",
        )
        _create_trace_score(
            lf=lf,
            trace_id=trace_id,
            name="active_failure_count",
            value=float(len(state.active_failures)),
            comment=(
                f"Active MAST failure modes: "
                f"{', '.join(state.active_failures) if state.active_failures else 'none'}"
            ),
        )
        _create_trace_score(
            lf=lf,
            trace_id=trace_id,
            name="is_terminal",
            value=1.0 if state.is_terminal else 0.0,
            data_type="BOOLEAN",
            comment=state.terminal_reason if state.is_terminal else "Agent operational",
        )
    except Exception as exc:
        print(f"[Langfuse] trace_degrading_agent failed: {exc}")


def flush() -> None:
    """Drain all pending Langfuse events. Call at process shutdown."""
    lf = _client()
    if lf is None:
        return
    try:
        lf.flush()
    except Exception:
        pass
