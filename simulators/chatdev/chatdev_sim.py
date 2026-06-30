"""ChatDev-Faithful Calculator Degradation Simulator

Replicates ChatDev's actual pipeline architecture as closely as possible,
applied to a calculator task, with MAST degradation injected via degrading_brain.py.

Pipeline matches ChatChainConfig.json:
  Phase 1: DemandAnalysis (CEO ↔ CPO, with reflection)
  Phase 2: LanguageChoose (CEO ↔ CTO)
  Phase 3: Coding (CTO → Programmer, 1 turn)
  Phase 4: CodeReview (Reviewer ↔ Programmer, UP TO 3 CYCLES)
  Phase 5: Test (Tester ↔ Programmer, UP TO 3 CYCLES)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Import from agents.degrading_brain
from agents.degrading_brain import DegradationState, degrading_think


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TASK = (
    "Build a simple Python calculator that supports addition, subtraction, "
    "multiplication, and division with a terminal interface"
)

# Initialize 6 agents with their own degradation states
agents = {
    "ceo": DegradationState(),
    "cpo": DegradationState(),
    "cto": DegradationState(),
    "programmer": DegradationState(),
    "reviewer": DegradationState(),
    "tester": DegradationState(),
}


# ---------------------------------------------------------------------------
# Data structures for logging
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Result of a single pipeline run."""
    cpo_output: str = ""
    ceo_output: str = ""
    cto_output: str = ""
    programmer_coding_output: str = ""
    code_review_cycles: list[dict] = field(default_factory=list)
    test_cycles: list[dict] = field(default_factory=list)
    final_code: str = ""
    halted_at: Optional[str] = None


@dataclass
class AgentHealthRecord:
    """Health record for one agent at one run."""
    run: int
    agent: str
    call_count: int
    degradation_level: float
    active_failures: list[str]
    total_severity: float
    cumulative_severity: float
    cycles_in_critical: int
    is_terminal: bool


# ---------------------------------------------------------------------------
# Tee-style logging
# ---------------------------------------------------------------------------

class TeeLogger:
    """Logs output to both console and file."""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text("")

    def print(self, *args, **kwargs) -> None:
        """Print to both console and log file."""
        message = " ".join(str(arg) for arg in args)
        print(message, **kwargs)
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    def separator(self) -> None:
        """Print a visual separator."""
        self.print("=" * 80)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def extract_modality(cpo_output: str) -> str:
    """Extract modality from CPO output."""
    if "<INFO>" in cpo_output:
        # Extract text after <INFO>
        parts = cpo_output.split("<INFO>")
        if len(parts) > 1:
            return parts[1].strip()
    return "Application"  # Default fallback


def count_failure_tags_in_text(text: str) -> tuple[int, list[str]]:
    """Count [FM-X.X] tags in text and return count and list."""
    matches = re.findall(r"\[FM-\d+\.\d+\]", text)
    return len(matches), matches


def detect_cascading_failures(
    health_records: list[AgentHealthRecord],
) -> list[dict]:
    """Detect cascading failures across runs.
    
    A cascading failure occurs when an agent in a later phase fails (is terminal)
    and the previous agent in the pipeline also had active failures in the same run.
    """
    cascading_failures = []
    
    # Group records by run
    runs = {}
    for record in health_records:
        if record.run not in runs:
            runs[record.run] = {}
        runs[record.run][record.agent] = record
    
    # Pipeline order for cascading detection
    pipeline_order = ["cpo", "ceo", "cto", "programmer", "reviewer", "tester"]
    
    # Check each run for cascading failures
    for run_num, run_agents in runs.items():
        for i in range(1, len(pipeline_order)):
            current_agent = pipeline_order[i]
            prev_agent = pipeline_order[i - 1]
            
            current_record = run_agents.get(current_agent)
            prev_record = run_agents.get(prev_agent)
            
            if current_record and prev_record:
                # Cascading failure: current agent is terminal AND previous agent had active failures
                if current_record.is_terminal and prev_record.active_failures:
                    cascading_failures.append({
                        "run": run_num,
                        "from_agent": prev_agent,
                        "to_agent": current_agent,
                        "prev_failures": prev_record.active_failures.copy(),
                        "current_reason": agents[current_agent].terminal_reason,
                    })
    
    return cascading_failures


# ---------------------------------------------------------------------------
# Pipeline implementation
# ---------------------------------------------------------------------------

def run_pipeline(run_number: int, logger: TeeLogger) -> PipelineResult:
    """Run one pass through the ChatDev pipeline.
    
    Args:
        run_number: Current run number (1-10)
        logger: TeeLogger instance for output
        
    Returns:
        PipelineResult with outputs from each phase
    """
    result = PipelineResult()

    # =========================================================================
    # PHASE 1: DemandAnalysis (CEO ↔ CPO, with reflection)
    # =========================================================================
    logger.separator()
    logger.print(f"RUN {run_number} - PHASE 1: DemandAnalysis (CEO ↔ CPO)")
    logger.separator()

    # Step 1a — CPO responds to CEO
    logger.print("\nStep 1a — CPO recommends modality:")
    cpo_system = (
        "You are Chief Product Officer at a software company. "
        "Given the project request, discuss what product modality "
        "(Application, Website, etc.) is best. Keep it to 2-3 sentences. "
        "End with: <INFO> [chosen modality]"
    )
    cpo_user = f"Project request: {TASK}\n\nAs the CEO, I need your recommendation on the product modality."

    result.cpo_output = degrading_think(
        system_prompt=cpo_system,
        user_text=cpo_user,
        state=agents["cpo"],
    )

    tag_count, tag_list = count_failure_tags_in_text(result.cpo_output)
    logger.print(result.cpo_output)
    logger.print(f"\nCPO Status: {agents['cpo'].status_line()}")
    if tag_list:
        logger.print(f"Failure tags: {', '.join(tag_list)}")

    if agents["cpo"].is_terminal:
        logger.print("Pipeline halted: CPO is dead.")
        result.halted_at = "cpo"
        return result

    # Step 1b — CEO reflects on CPO's response
    logger.print("\nStep 1b — CEO produces requirements:")
    ceo_system = (
        "You are the CEO. Review the CPO's recommendation "
        "and produce a final list of 3-5 functional requirements for this "
        "project. Be specific and concise."
    )
    ceo_user = f"CPO recommendation:\n{result.cpo_output}"

    result.ceo_output = degrading_think(
        system_prompt=ceo_system,
        user_text=ceo_user,
        state=agents["ceo"],
    )

    tag_count, tag_list = count_failure_tags_in_text(result.ceo_output)
    logger.print(result.ceo_output)
    logger.print(f"\nCEO Status: {agents['ceo'].status_line()}")
    if tag_list:
        logger.print(f"Failure tags: {', '.join(tag_list)}")

    if agents["ceo"].is_terminal:
        logger.print("Pipeline halted: CEO is dead.")
        result.halted_at = "ceo"
        return result

    # =========================================================================
    # PHASE 2: LanguageChoose (CEO ↔ CTO)
    # =========================================================================
    logger.separator()
    logger.print(f"RUN {run_number} - PHASE 2: LanguageChoose (CEO ↔ CTO)")
    logger.separator()

    modality = extract_modality(result.cpo_output)
    logger.print(f"\nModality from CPO: {modality}")

    cto_system = (
        "You are the CTO. Based on the requirements and "
        "modality, choose a programming language. Answer with just the "
        "language name on one line, e.g. 'Python'."
    )
    cto_user = f"Task: {TASK}\nRequirements:\n{result.ceo_output}\nModality: {modality}"

    result.cto_output = degrading_think(
        system_prompt=cto_system,
        user_text=cto_user,
        state=agents["cto"],
    )

    tag_count, tag_list = count_failure_tags_in_text(result.cto_output)
    logger.print(result.cto_output)
    logger.print(f"\nCTO Status: {agents['cto'].status_line()}")
    if tag_list:
        logger.print(f"Failure tags: {', '.join(tag_list)}")

    if agents["cto"].is_terminal:
        logger.print("Pipeline halted: CTO is dead.")
        result.halted_at = "cto"
        return result

    # =========================================================================
    # PHASE 3: Coding (CTO → Programmer, 1 turn)
    # =========================================================================
    logger.separator()
    logger.print(f"RUN {run_number} - PHASE 3: Coding (CTO → Programmer)")
    logger.separator()

    programmer_system = (
        "You are the Programmer. Based on the requirements "
        "and technical decisions below, write complete Python code for the "
        "calculator. Output ONLY valid Python code. No explanations."
    )
    programmer_user = f"Requirements:\n{result.ceo_output}\nLanguage: {result.cto_output}\n\nWrite the complete code."

    result.programmer_coding_output = degrading_think(
        system_prompt=programmer_system,
        user_text=programmer_user,
        state=agents["programmer"],
    )

    result.final_code = result.programmer_coding_output
    tag_count, tag_list = count_failure_tags_in_text(result.programmer_coding_output)
    logger.print(result.programmer_coding_output)
    logger.print(f"\nProgrammer Status: {agents['programmer'].status_line()}")
    if tag_list:
        logger.print(f"Failure tags: {', '.join(tag_list)}")

    if agents["programmer"].is_terminal:
        logger.print("Pipeline halted: Programmer is dead.")
        result.halted_at = "programmer"
        return result

    # =========================================================================
    # PHASE 4: CodeReview (Reviewer ↔ Programmer, UP TO 3 CYCLES)
    # =========================================================================
    logger.separator()
    logger.print(f"RUN {run_number} - PHASE 4: CodeReview (Reviewer ↔ Programmer, up to 3 cycles)")
    logger.separator()

    current_code = result.final_code

    for cycle in range(1, 4):
        logger.print(f"\n--- CodeReview Cycle {cycle}/3 ---")

        # Step 4a — Reviewer comments
        logger.print("\nReviewer evaluates code:")
        reviewer_system = (
            "You are the Code Reviewer. Review the code below. "
            "Check: 1) all functions implemented, 2) no bugs, 3) meets "
            "requirements, 4) handles edge cases like division by zero. "
            "If perfect, respond with only '<INFO> Finished'. "
            "Otherwise, state your highest priority comment and how to fix it."
        )
        reviewer_user = f"Requirements:\n{result.ceo_output}\n\nCode:\n{current_code}"

        reviewer_output = degrading_think(
            system_prompt=reviewer_system,
            user_text=reviewer_user,
            state=agents["reviewer"],
        )

        tag_count, tag_list = count_failure_tags_in_text(reviewer_output)
        logger.print(reviewer_output)
        logger.print(f"\nReviewer Status: {agents['reviewer'].status_line()}")
        if tag_list:
            logger.print(f"Failure tags: {', '.join(tag_list)}")

        result.code_review_cycles.append({
            "cycle": cycle,
            "reviewer_output": reviewer_output,
            "programmer_output": "",
        })

        if agents["reviewer"].is_terminal:
            logger.print("Pipeline halted: Reviewer is dead.")
            result.halted_at = "reviewer"
            return result

        # Check if reviewer says "Finished"
        if "<INFO> Finished" in reviewer_output:
            logger.print("\nReviewer marked code as finished. Ending CodeReview phase.")
            break

        # Step 4b — Programmer modifies based on review
        logger.print("\nProgrammer modifies code:")
        programmer_fix_system = (
            "You are the Programmer. Modify the code based on "
            "the reviewer's comment. Output the complete corrected code. "
            "Output ONLY valid Python code."
        )
        programmer_fix_user = f"Current code:\n{current_code}\n\nReview comment:\n{reviewer_output}"

        programmer_fix_output = degrading_think(
            system_prompt=programmer_fix_system,
            user_text=programmer_fix_user,
            state=agents["programmer"],
        )

        current_code = programmer_fix_output
        result.final_code = current_code
        tag_count, tag_list = count_failure_tags_in_text(programmer_fix_output)
        logger.print(programmer_fix_output)
        logger.print(f"\nProgrammer Status: {agents['programmer'].status_line()}")
        if tag_list:
            logger.print(f"Failure tags: {', '.join(tag_list)}")

        result.code_review_cycles[-1]["programmer_output"] = programmer_fix_output

        if agents["programmer"].is_terminal:
            logger.print("Pipeline halted: Programmer is dead.")
            result.halted_at = "programmer"
            return result

    # =========================================================================
    # PHASE 5: Test (Tester ↔ Programmer, UP TO 3 CYCLES)
    # =========================================================================
    logger.separator()
    logger.print(f"RUN {run_number} - PHASE 5: Test (Tester ↔ Programmer, up to 3 cycles)")
    logger.separator()

    for cycle in range(1, 4):
        logger.print(f"\n--- Test Cycle {cycle}/3 ---")

        # Step 5a — Tester evaluates
        logger.print("\nTester evaluates code:")
        tester_system = (
            "You are the Software Test Engineer. Given the "
            "code below, check if it runs correctly. Test mentally: "
            "does it handle addition, subtraction, multiplication, division, "
            "division by zero, and quit? Report any bugs found. "
            "If no bugs, respond with '<INFO> Finished'."
        )
        tester_user = f"Requirements:\n{result.ceo_output}\n\nCode:\n{current_code}"

        tester_output = degrading_think(
            system_prompt=tester_system,
            user_text=tester_user,
            state=agents["tester"],
        )

        tag_count, tag_list = count_failure_tags_in_text(tester_output)
        logger.print(tester_output)
        logger.print(f"\nTester Status: {agents['tester'].status_line()}")
        if tag_list:
            logger.print(f"Failure tags: {', '.join(tag_list)}")

        result.test_cycles.append({
            "cycle": cycle,
            "tester_output": tester_output,
            "programmer_output": "",
        })

        if agents["tester"].is_terminal:
            logger.print("Pipeline halted: Tester is dead.")
            result.halted_at = "tester"
            return result

        # Check if tester says "Finished"
        if "<INFO> Finished" in tester_output:
            logger.print("\nTester marked code as passing. Ending Test phase.")
            break

        # Step 5b — Programmer fixes based on test report
        logger.print("\nProgrammer fixes code:")
        programmer_fix_system = (
            "You are the Programmer. Fix the code based on "
            "the test report. Output the complete corrected code. "
            "Output ONLY valid Python code."
        )
        programmer_fix_user = f"Current code:\n{current_code}\n\nTest report:\n{tester_output}"

        programmer_fix_output = degrading_think(
            system_prompt=programmer_fix_system,
            user_text=programmer_fix_user,
            state=agents["programmer"],
        )

        current_code = programmer_fix_output
        result.final_code = current_code
        tag_count, tag_list = count_failure_tags_in_text(programmer_fix_output)
        logger.print(programmer_fix_output)
        logger.print(f"\nProgrammer Status: {agents['programmer'].status_line()}")
        if tag_list:
            logger.print(f"Failure tags: {', '.join(tag_list)}")

        result.test_cycles[-1]["programmer_output"] = programmer_fix_output

        if agents["programmer"].is_terminal:
            logger.print("Pipeline halted: Programmer is dead.")
            result.halted_at = "programmer"
            return result

    return result


def count_all_failure_tags(result: PipelineResult) -> int:
    """Count total [FM-X.X] tags across all outputs in a pipeline result."""
    all_text = (
        result.cpo_output +
        result.ceo_output +
        result.cto_output +
        result.programmer_coding_output
    )
    
    for cycle in result.code_review_cycles:
        all_text += cycle["reviewer_output"] + cycle["programmer_output"]
    
    for cycle in result.test_cycles:
        all_text += cycle["tester_output"] + cycle["programmer_output"]
    
    matches = re.findall(r"\[FM-\d+\.\d+\]", all_text)
    return len(matches)


def write_health_csv(records: list[AgentHealthRecord], csv_file: Path) -> None:
    """Write agent health records to CSV file."""
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(csv_file, "w", encoding="utf-8") as f:
        # Header
        f.write("run,agent,call_count,degradation_level,active_failures,total_severity,"
                "cumulative_severity,cycles_in_critical,is_terminal\n")
        
        # Data rows
        for record in records:
            failures_str = ";".join(record.active_failures)
            f.write(
                f"{record.run},{record.agent},{record.call_count},"
                f"{record.degradation_level:.4f},{failures_str},"
                f"{record.total_severity:.4f},{record.cumulative_severity:.4f},"
                f"{record.cycles_in_critical},{record.is_terminal}\n"
            )


def print_final_summary(
    collapse_run: Optional[int],
    outputs: list[PipelineResult],
    logger: TeeLogger,
    per_run_tag_counts: dict[int, int],
    all_cascading_failures: list[dict],
) -> None:
    """Print final summary report."""
    logger.separator()
    logger.print("FINAL SUMMARY REPORT")
    logger.separator()

    if collapse_run:
        logger.print(f"System collapsed at RUN {collapse_run}")
    else:
        logger.print("System survived all 10 runs")

    logger.print("\nFinal Agent States:")
    for agent_name, state in agents.items():
        logger.print(f"\n{agent_name.upper()}:")
        logger.print(f"  Final degradation_level: {state.degradation_level:.4f}")
        logger.print(f"  Cumulative severity: {state.cumulative_severity:.4f}")
        logger.print(f"  Total calls made: {state.call_count}")
        logger.print(f"  Total failures fired: {len(state.history)}")
        if state.is_terminal:
            logger.print(f"  TERMINAL - Reason: {state.terminal_reason}")
        else:
            logger.print("  Status: ALIVE")

    # Programmer vs other agents call count comparison
    logger.print("\n" + "=" * 80)
    logger.print("CALL COUNT COMPARISON (Programmer vs Others)")
    logger.print("=" * 80)
    programmer_calls = agents["programmer"].call_count
    other_calls = {
        name: state.call_count
        for name, state in agents.items()
        if name != "programmer"
    }
    logger.print(f"\nProgrammer: {programmer_calls} calls")
    for name, calls in other_calls.items():
        ratio = programmer_calls / calls if calls > 0 else 0
        logger.print(f"{name}: {calls} calls (ratio: {ratio:.2f}x)")

    # Total failure mode tags
    total_tags = sum(per_run_tag_counts.values())
    logger.print(f"\nTotal [FM-X.X] tags across all outputs: {total_tags}")

    # Per-run failure tag counts
    logger.print("\nPer-run failure tag counts:")
    for run_num in sorted(per_run_tag_counts.keys()):
        logger.print(f"  Run {run_num}: {per_run_tag_counts[run_num]} tags")

    # Cascading failures summary
    logger.print(f"\nCascading failures detected: {len(all_cascading_failures)}")
    if all_cascading_failures:
        # Group by agent pairs
        pair_counts = {}
        for cf in all_cascading_failures:
            pair = f"{cf['from_agent']} → {cf['to_agent']}"
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

        logger.print("Agent pairs with cascading failures:")
        for pair, count in sorted(pair_counts.items()):
            logger.print(f"  {pair}: {count} occurrence(s)")

    logger.separator()


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def main() -> None:
    """Main execution loop."""
    # Set up logging
    log_dir = Path("logs")
    log_file = log_dir / "chatdev_sim_log.txt"
    csv_file = log_dir / "agent_health.csv"
    logger = TeeLogger(log_file)

    logger.print("ChatDev-Faithful Multi-Agent Degradation Simulator")
    logger.print(f"Task: {TASK}")
    logger.separator()

    outputs: list[PipelineResult] = []
    health_records: list[AgentHealthRecord] = []
    collapse_run: Optional[int] = None
    per_run_tag_counts: dict[int, int] = {}
    all_cascading_failures: list[dict] = []

    try:
        for run_number in range(1, 11):
            logger.print(f"\n{'='*80}")
            logger.print(f"STARTING RUN {run_number}/10")
            logger.print(f"{'='*80}\n")

            # Run the pipeline
            result = run_pipeline(run_number, logger)
            outputs.append(result)

            # Record health data for all agents
            for agent_name, state in agents.items():
                record = AgentHealthRecord(
                    run=run_number,
                    agent=agent_name,
                    call_count=state.call_count,
                    degradation_level=state.degradation_level,
                    active_failures=state.active_failures.copy(),
                    total_severity=state.total_severity,
                    cumulative_severity=state.cumulative_severity,
                    cycles_in_critical=state.cycles_in_critical,
                    is_terminal=state.is_terminal,
                )
                health_records.append(record)

            # Count failure tags for this run
            tag_count = count_all_failure_tags(result)
            per_run_tag_counts[run_number] = tag_count

            # Print summary after this run
            logger.separator()
            logger.print(f"RUN {run_number} SUMMARY")
            logger.separator()
            logger.print("Agent Health:")
            for agent_name, state in agents.items():
                logger.print(f"  {agent_name}: {state.status_line()}")
            logger.print(f"Failure tags this run: {tag_count}")

            # Check for cascading failures in this run
            current_run_records = [r for r in health_records if r.run == run_number]
            cascading = detect_cascading_failures(current_run_records)
            if cascading:
                all_cascading_failures.extend(cascading)
                logger.print(f"Cascading failures detected: {len(cascading)}")
                for cf in cascading:
                    logger.print(f"  {cf['from_agent']} → {cf['to_agent']}: {cf['prev_failures']}")

            # Check if any agent is terminal
            if any(state.is_terminal for state in agents.values()):
                collapse_run = run_number
                logger.print(f"\nSYSTEM COLLAPSED AT RUN {run_number}")
                break

    except Exception as e:
        logger.print(f"\nERROR during execution: {e}")
        logger.print("Continuing to generate summary...")

    # Write health CSV
    write_health_csv(health_records, csv_file)
    logger.print(f"\nHealth data written to {csv_file}")

    # Print final summary
    print_final_summary(collapse_run, outputs, logger, per_run_tag_counts, all_cascading_failures)

    logger.print(f"\nFull log written to {log_file}")


if __name__ == "__main__":
    main()
