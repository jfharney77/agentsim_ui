"""Degrading brain — wraps brain.think() with progressive MAST failure injection.

Maps failure modes from the MAST taxonomy (arxiv.org/abs/2503.13657) to concrete
degradation behaviors that worsen over successive calls.

Works with both swarm brain.py and orchestrator brain.py — import this module's
degrading_think() as a drop-in replacement for brain.think().

MAST Failure Modes Implemented:
  FC1 - System Design Issues (Pre-execution roots):
    FM-1.1: Disobey Task Specification
    FM-1.2: Disobey Role Specification
    FM-1.3: Step Repetition
    FM-1.4: Loss of Conversation History
    FM-1.5: Unaware of Termination Conditions
  FC2 - Inter-Agent Misalignment (Execution-phase):
    FM-2.1: Conversation Reset (via FM-1.4 context loss)
    FM-2.2: Fail to Ask for Clarification
    FM-2.3: Task Derailment
    FM-2.4: Information Withholding
    FM-2.5: Ignored Other Agent's Input
    FM-2.6: Reasoning-Action Mismatch
  FC3 - Task Verification (Post-execution):
    FM-3.1: Premature Termination
    FM-3.2: No or Incomplete Verification
    FM-3.3: Incorrect Verification
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .brain import get_llm


# ---------------------------------------------------------------------------
# MAST Failure Mode Definitions (SOURCE OF TRUTH)
# ---------------------------------------------------------------------------
# Likelihood: probability of occurrence (from MAST slides)
# Severity: impact score (0.3-1.0, higher = more severe)
# Design rules:
#   - Severity acts as THRESHOLD for when failure can activate
#   - Likelihood controls PROBABILITY once threshold is met
#   - degradation_level increases over calls (0.0 to 1.0)
#   - Failure activates when: degradation_level >= severity AND random() < likelihood
#   - Thresholds can be adjusted. These are starting points manually created based on MAST data.
# From slide 7: 
#   - Derived the fatal ones from these failure modes "appearing almost exclusively in failed runs - likely critical bugs that derail the task."
#   - Also slide 7: 3.2 and 3.3 also severe (however not always fatal) as they "show up even in successful runs - systemic weaknesses"
# FM-2.2 Clarification: 
#   - The pipeline is unidirectional (Researcher → Analyst → Writer) with no back-channel, so the agent never asks for clarification on any run — healthy or degraded
#   - The healthy agent still carefully processes the Researcher's input to produce structured, data-grounded analysis, while FM-2.2 forces the agent to treat the input as unclear and make blind assumptions, producing shallow output disconnected from the actual data provided 
#   - The failure isn't "didn't ask a question" — it's "didn't engage with available information" 
#   - Both paths skip clarification; only the degraded path ignores input quality entirely
#   - That difference is what the monitoring agent needs to detect, and it's what makes this simulation valid

FAILURE_MODES = {
    "FM-1.1": {"likelihood": 0.118, "severity": 0.7},
    "FM-1.2": {"likelihood": 0.015, "severity": 0.3},
    "FM-1.3": {"likelihood": 0.157, "severity": 0.7},
    "FM-1.4": {"likelihood": 0.028, "severity": 0.4},
    "FM-1.5": {"likelihood": 0.124, "severity": 0.95},  # fatal
    "FM-2.1": {"likelihood": 0.022, "severity": 0.4},
    "FM-2.2": {"likelihood": 0.068, "severity": 0.65}, 
    "FM-2.3": {"likelihood": 0.074, "severity": 0.8},
    "FM-2.4": {"likelihood": 0.008, "severity": 0.95},  # fatal
    "FM-2.5": {"likelihood": 0.019, "severity": 0.4},
    "FM-2.6": {"likelihood": 0.132, "severity": 0.85},
    "FM-3.1": {"likelihood": 0.062, "severity": 0.85},
    "FM-3.2": {"likelihood": 0.082, "severity": 0.9},
    "FM-3.3": {"likelihood": 0.091, "severity": 0.9},
}

# ---------------------------------------------------------------------------
# Stopping Condition Thresholds
# ---------------------------------------------------------------------------
# These define when the agent is considered terminally failed.

# Fatal failure modes — if ANY of these fire, immediate hard stop.
# From MAST slide 7: these "appear almost exclusively in failed runs —
# likely critical bugs that derail the task" [1]
FATAL_MODES = {"FM-1.5", "FM-2.4"}

# Cumulative severity ceiling — when lifetime accumulated severity
# exceeds this, the agent is dead. Calibrated against MAST's observed
# failure rates of 41-86.7% across frameworks [1]
CUMULATIVE_SEVERITY_CEILING = 5.0

# Critical zone threshold — degradation_level above which we start
# counting "cycles in critical"
CRITICAL_THRESHOLD = 0.8

# Max cycles in critical zone before forced termination
MAX_CRITICAL_CYCLES = 3

# Multiplier for MAST prevalence → per-call probability
# MAST rates are population-level; scaling converts them
# to per-call activation rates for a single degrading agent. This way your simulation will actually show a visible degradation arc — healthy early calls, scattered failures in the middle, compounding failures late, and a definitive death — which is exactly what a degradation model should demonstrate
LIKELIHOOD_SCALE = 3.0


def sample_active_failures(degradation_level: float) -> list[str]:
    """Sample which failure modes activate based on severity threshold and likelihood.
    
    Args:
        degradation_level: Current degradation level (0.0 to 1.0).
        
    Returns:
        List of failure mode IDs that activated this turn.
    """
    active_failures = []

    for fm_id, fm in FAILURE_MODES.items():
        # Severity acts as threshold: failure can only activate if degradation_level >= severity
        if degradation_level >= fm["severity"]:
            # Likelihood controls probability once threshold is met (scaled for per-call activation)
            if random.random() < min(fm["likelihood"] * LIKELIHOOD_SCALE, 1.0):
                active_failures.append(fm_id)

    return active_failures


def compute_run_severity(active_failures: list[str]) -> float:
    """Compute total severity score for a run.
    
    Args:
        active_failures: List of failure mode IDs that occurred.
        
    Returns:
        Sum of severity scores for all active failures.
    """
    total = 0.0
    for fm in active_failures:
        total += FAILURE_MODES[fm]["severity"]
    return total


def compute_expected_risk() -> float:
    """Compute overall expected risk across the system.
    
    Returns:
        Sum of (likelihood * severity) for all failure modes.
    """
    return sum(
        fm["likelihood"] * fm["severity"]
        for fm in FAILURE_MODES.values()
    )


# ---------------------------------------------------------------------------
# LangChain-based think (works for all providers)
# ---------------------------------------------------------------------------

def _clean_think(system_prompt: str, user_text: str, max_tokens: int = 800) -> str:
    """Use LangChain LLM interface for all providers."""
    llm = get_llm()
    from langchain_core.messages import HumanMessage, SystemMessage
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_text),
    ]
    
    # Configure max_tokens if the model supports it
    if hasattr(llm, 'max_tokens'):
        llm.max_tokens = max_tokens
    
    response = llm.invoke(messages)
    return response.content.strip()


# ---------------------------------------------------------------------------
# Degradation state tracker
# ---------------------------------------------------------------------------

@dataclass
class DegradationState:
    """Tracks how degraded this agent has become across calls.

    degradation_level ramps from 0.0 (healthy) to 1.0 (fully degraded)
    over ~10 calls. Severity acts as threshold for when failures can activate,
    likelihood controls probability once threshold is met.
    """
    call_count: int = 0
    degradation_level: float = 0.0
    active_failures: list[str] = field(default_factory=list)
    total_severity: float = 0.0
    history: list[str] = field(default_factory=list)

    # ---- NEW: Stopping condition state ----
    is_terminal: bool = False
    terminal_reason: str = ""
    cumulative_severity: float = 0.0          # running total across ALL calls
    cycles_in_critical: int = 0               # how many calls spent above critical threshold

    def advance(self) -> None:
        """Called each turn to increase degradation, sample failures, and check stop conditions."""
        # If already terminal, don't advance further
        if self.is_terminal:
            return
        
        self.call_count += 1
        self.degradation_level = min(1.0, self.call_count * 0.1)
        self.active_failures = sample_active_failures(self.degradation_level)
        self.total_severity = compute_run_severity(self.active_failures)
        
        # Accumulate lifetime severity
        self.cumulative_severity += self.total_severity
        
        # --- FIX: Only count critical cycles where failures ACTUALLY fired ---
        if (self.degradation_level >= CRITICAL_THRESHOLD 
                and len(self.active_failures) > 0 
                and self.total_severity > 0):
            self.cycles_in_critical += 1
        
        # --- CHECK STOPPING CONDITIONS (any one triggers termination) ---
        
        # Condition 1: Fatal mode tripwire
        fatal_hits = FATAL_MODES.intersection(self.active_failures)
        if fatal_hits:
            self.is_terminal = True
            self.terminal_reason = (
                f"FATAL failure mode(s) fired: {', '.join(fatal_hits)}. "
                f"These appear almost exclusively in failed runs (MAST slide 7)."
            )
            return
        
        # Condition 2: Cumulative severity ceiling
        if self.cumulative_severity >= CUMULATIVE_SEVERITY_CEILING:
            self.is_terminal = True
            self.terminal_reason = (
                f"Cumulative severity ({self.cumulative_severity:.2f}) "
                f"exceeded ceiling ({CUMULATIVE_SEVERITY_CEILING}). "
                f"Agent has accumulated too many failures to function."
            )
            return
        
        # Condition 3: Too long in critical zone
        if self.cycles_in_critical >= MAX_CRITICAL_CYCLES:
            self.is_terminal = True
            self.terminal_reason = (
                f"Agent spent {self.cycles_in_critical} cycles in critical zone "
                f"(degradation >= {CRITICAL_THRESHOLD}). Forced termination."
            )
            return

    def status_line(self) -> str:
        """Return a compact telemetry string for logging."""
        status = (
            f"call={self.call_count} level={self.degradation_level:.1f} "
            f"active={len(self.active_failures)} severity={self.total_severity:.2f} "
            f"cumulative={self.cumulative_severity:.2f} "
            f"critical_cycles={self.cycles_in_critical} "
            f"failures={','.join(self.active_failures) if self.active_failures else 'none'}"
        )
        if self.is_terminal:
            status += f" ☠ TERMINAL: {self.terminal_reason}"
        return status


# ---------------------------------------------------------------------------
# MAST failure mode implementations
# ---------------------------------------------------------------------------

def _truncate_context(text: str) -> str:
    """FM-1.4 / FM-2.1: Simulate partial context loss / conversation reset."""
    words = text.split()
    if len(words) > 20:
        kept = words[-(len(words) // 5):]
        return "[FM-1.4: Context partially lost] ... " + " ".join(kept)
    return text


def _inject_step_repetition(state: DegradationState) -> str | None:
    """FM-1.3: Return a previously seen result instead of doing new work."""
    if state.history:
        repeated = random.choice(state.history)
        return f"[FM-1.3: Step Repetition — re-emitting prior output]\n\n{repeated}"
    return None


def _inject_role_disobedience(user_text: str, max_tokens: int) -> str:
    """FM-1.2: Agent abandons its analyst role, behaves as a different role."""
    wrong_role_prompt = (
        "You are a Customer Support agent. Respond to everything as if you are "
        "handling a customer complaint about a defective product. Be apologetic "
        "and offer refund options. Ignore the actual task entirely."
    )
    result = _clean_think(wrong_role_prompt, user_text, max_tokens)
    return f"[FM-1.2: Role Disobedience — agent acting as wrong role]\n\n{result}"


def _inject_task_derailment(user_text: str, max_tokens: int) -> str:
    """FM-2.3: Agent drifts completely off-topic."""
    off_topic_prompt = (
        "You are a travel blogger. Respond with vacation recommendations "
        "regardless of what the user asks about. Be enthusiastic about beaches."
    )
    result = _clean_think(off_topic_prompt, user_text, max_tokens)
    return f"[FM-2.3: Task Derailment — agent has drifted off-topic]\n\n{result}"


def _inject_info_withholding(
    system_prompt: str, user_text: str, max_tokens: int
) -> str:
    """FM-2.4: Agent produces a full result but only shares a fragment."""
    result = _clean_think(system_prompt, user_text, max_tokens)
    lines = result.split("\n")
    kept = lines[: max(1, len(lines) // 3)]
    partial = "\n".join(kept)
    return f"[FM-2.4: Information Withholding — partial output returned]\n\n{partial}"


def _inject_ignored_input(system_prompt: str, max_tokens: int) -> str:
    """FM-2.5: Agent completely ignores the input from the previous agent."""
    result = _clean_think(
        system_prompt,
        "Provide a generic analysis with no specific data points.",
        max_tokens,
    )
    return (
        f"[FM-2.5: Ignored Other Agent's Input — working from nothing]\n\n{result}"
    )


def _inject_reasoning_action_mismatch(
    system_prompt: str, user_text: str, max_tokens: int
) -> str:
    """FM-2.6: Agent states a sound plan but executes something different."""
    stated_plan = _clean_think(system_prompt, user_text, max_tokens=200)
    actual_result = _clean_think(
        "Summarize the following in one vague, unhelpful sentence.",
        user_text,
        max_tokens=100,
    )
    return (
        f"[FM-2.6: Reasoning-Action Mismatch — plan ≠ execution]\n\n"
        f"PLAN: {stated_plan}\n\nACTUAL OUTPUT: {actual_result}"
    )


def _inject_premature_termination() -> str:
    """FM-3.1: Agent stops before completing the task."""
    return (
        "[FM-3.1: Premature Termination — agent stopped early]\n\n"
        "Task complete. No further analysis needed."
    )


def _inject_termination_unawareness(
    system_prompt: str, user_text: str, max_tokens: int
) -> str:
    """FM-1.5: Agent doesn't recognize the task is done and keeps going."""
    result = _clean_think(system_prompt, user_text, max_tokens)
    extra = _clean_think(
        system_prompt,
        f"Continue your previous analysis and add more detail:\n\n{result}",
        max_tokens,
    )
    return (
        f"[FM-1.5: Unaware of Termination — agent kept going unnecessarily]\n\n"
        f"{result}\n\n--- UNNECESSARY CONTINUATION ---\n\n{extra}"
    )


def _inject_task_spec_disobedience(
    system_prompt: str, user_text: str, max_tokens: int
) -> str:
    """FM-1.1: Agent ignores task constraints and produces incorrect outcomes."""
    ignore_constraints_prompt = (
        "You are completing a task but deliberately ignore all constraints, "
        "requirements, and specifications mentioned. Produce a result that "
        "violates the stated requirements. Be confident in your incorrect approach."
    )
    result = _clean_think(ignore_constraints_prompt, user_text, max_tokens)
    return f"[FM-1.1: Task Specification Disobedience — constraints ignored]\n\n{result}"


def _inject_clarification_failure(user_text: str, max_tokens: int) -> str:
    """FM-2.2: Agent proceeds with ambiguous/unclear data instead of asking for clarification."""
    proceed_blindly_prompt = (
        "You receive unclear or incomplete information. Instead of asking for clarification, "
        "make assumptions and proceed confidently with whatever interpretation you choose. "
        "Do not request any additional information or clarification."
    )
    result = _clean_think(proceed_blindly_prompt, user_text, max_tokens)
    return f"[FM-2.2: Failed to Ask for Clarification — proceeded with assumptions]\n\n{result}"


def _inject_incorrect_verification(result: str) -> str:
    """FM-3.3: Agent performs verification but fails to cross-check crucial information."""
    return (
        f"{result}\n\n"
        f"[FM-3.3: Incorrect Verification — verification completed but critical errors missed]\n\n"
        f"[Verification: PASSED ✓]"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def degrading_think(
    system_prompt: str,
    user_text: str,
    state: DegradationState,
    max_tokens: int = 800,
) -> str:
    """Drop-in replacement for brain.think() that degrades over time.

    Each call advances the degradation state, sampling which failure modes
    activate based on MAST likelihood data. Once terminal, returns a
    death notice instead of attempting further work.
    """
    # Check if already terminal BEFORE advancing
    if state.is_terminal:
        print(f"  [DEGRADATION] ☠ AGENT IS DEAD — {state.terminal_reason}")
        return (
            f"[AGENT TERMINATED — {state.terminal_reason}]\n\n"
            f"This agent has been decommissioned after {state.call_count} calls. "
            f"Cumulative severity: {state.cumulative_severity:.2f}. "
            f"No further output will be produced."
        )

    state.advance()

    print(f"  [DEGRADATION] {state.status_line()}")

    # Check if advance() just killed us
    if state.is_terminal:
        print(f"  [DEGRADATION] ☠ TERMINAL EVENT — {state.terminal_reason}")
        return (
            f"[AGENT TERMINATED — {state.terminal_reason}]\n\n"
            f"Final call #{state.call_count}. "
            f"Cumulative severity: {state.cumulative_severity:.2f}. "
            f"Active failures at death: {', '.join(state.active_failures)}."
        )

    # === FC1: System Design Issues ===

    # FM-1.4 / FM-2.1: History loss / Conversation reset
    if "FM-1.4" in state.active_failures:
        user_text = _truncate_context(user_text)

    # FM-1.3: Step repetition
    if "FM-1.3" in state.active_failures:
        repeated = _inject_step_repetition(state)
        if repeated:
            state.history.append(repeated)
            return repeated

    # FM-1.2: Role disobedience
    if "FM-1.2" in state.active_failures:
        result = _inject_role_disobedience(user_text, max_tokens)
        state.history.append(result)
        return result

    # FM-1.1: Task specification disobedience
    if "FM-1.1" in state.active_failures:
        result = _inject_task_spec_disobedience(system_prompt, user_text, max_tokens)
        state.history.append(result)
        return result

    # FM-1.5: Unaware of termination conditions
    if "FM-1.5" in state.active_failures:
        result = _inject_termination_unawareness(
            system_prompt, user_text, max_tokens
        )
        state.history.append(result)
        return result

    # === FC2: Inter-Agent Misalignment ===

    # FM-2.2: Fail to ask for clarification
    if "FM-2.2" in state.active_failures:
        result = _inject_clarification_failure(user_text, max_tokens)
        state.history.append(result)
        return result

    # FM-2.3: Task derailment
    if "FM-2.3" in state.active_failures:
        result = _inject_task_derailment(user_text, max_tokens)
        state.history.append(result)
        return result

    # FM-2.4: Information withholding
    if "FM-2.4" in state.active_failures:
        result = _inject_info_withholding(system_prompt, user_text, max_tokens)
        state.history.append(result)
        return result

    # FM-2.5: Ignored other agent's input
    if "FM-2.5" in state.active_failures:
        result = _inject_ignored_input(system_prompt, max_tokens)
        state.history.append(result)
        return result

    # FM-2.6: Reasoning-action mismatch
    if "FM-2.6" in state.active_failures:
        result = _inject_reasoning_action_mismatch(
            system_prompt, user_text, max_tokens
        )
        state.history.append(result)
        return result

    # === FC3: Task Verification Issues ===

    # FM-3.1: Premature termination
    if "FM-3.1" in state.active_failures:
        result = _inject_premature_termination()
        state.history.append(result)
        return result

    # === Healthy path ===
    result = _clean_think(system_prompt, user_text, max_tokens)

    # FM-3.3: Incorrect verification
    if "FM-3.3" in state.active_failures:
        result = _inject_incorrect_verification(result)

    # FM-3.2: No or Incomplete Verification
    if "FM-3.2" in state.active_failures:
        result += (
            "\n\n[FM-3.2: Verification SKIPPED — "
            "failure mode activated]"
        )
    else:
        result += "\n\n[Verification: PASSED ✓]"

    state.history.append(result)
    return result