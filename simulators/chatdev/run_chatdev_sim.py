"""ChatDev-Faithful Calculator Degradation Simulator.

Runs the ChatDev pipeline 3 times for the same calculator task.
Agent DegradationStates persist across runs, so agents degrade 
over time. The Programmer degrades fastest because it gets called
most often (Coding + CodeReview modifications + Test modifications).

Output: ChatDev-format logs showing [FM-X.X] tags appearing and
multiplying across runs, with cascading failures visible in the
agent conversations.
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Import from engine (same directory)
from engine.chat_chain import ChatChain

TASK = (
    "Build a simple Python calculator that supports addition, "
    "subtraction, multiplication, and division. It should run in "
    "the terminal, prompt the user for two numbers and an operation, "
    "handle division by zero, and loop until the user types quit."
)


class ChatDevLogger:
    """Tee logger that matches ChatDev's [INFO] format [14]."""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("")
        self.utterance_count = 0
    
    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp} {level}] {message}"
        print(formatted)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    
    def log_chatting(self, phase_name: str, assistant_role: str, user_role: str,
                     task_prompt: str, phase_prompt: str, max_turn_step: int) -> None:
        """Log the [chatting] metadata table matching [14]."""
        self.log(f"System: **[chatting]**")
        self.log(f"| Parameter | Value |")
        self.log(f"| --- | --- |")
        self.log(f"| **task_prompt** | {task_prompt[:80]}... |")
        self.log(f"| **assistant_role_name** | {assistant_role} |")
        self.log(f"| **user_role_name** | {user_role} |")
        self.log(f"| **phase_name** | {phase_name} |")
        self.log(f"| **max_turn_step** | {max_turn_step} |")
    
    def log_role_playing(self, assistant_role: str, user_role: str) -> None:
        """Log the [RolePlaying] block matching [14]."""
        self.log(f"System: **[RolePlaying]**")
        self.log(f"| Parameter | Value |")
        self.log(f"| --- | --- |")
        self.log(f"| **assistant_role_name** | {assistant_role} |")
        self.log(f"| **user_role_name** | {user_role} |")
    
    def log_start_chat(self, role_name: str, role_prompt: str, message: str) -> None:
        """Log the [Start Chat] block matching [14]."""
        self.utterance_count += 1
        self.log(f"{role_name}: **[Start Chat]**")
        self.log(f"[{role_prompt[:200]}...]")
        self.log(message)
    
    def log_turn(self, assistant_role: str, user_role: str, phase_name: str, 
                 turn: float, role_prompt: str, message: str) -> None:
        """Log a conversation turn matching [14]."""
        self.utterance_count += 1
        self.log(f"{assistant_role}: **{assistant_role}<->{user_role} on : {phase_name}, turn {turn}**")
        self.log(f"[{role_prompt[:200]}...]")
        self.log(message)
    
    def log_seminar_conclusion(self, conclusion: str) -> None:
        """Log the [Seminar Conclusion] matching [14]."""
        self.log(f"**[Seminar Conclusion]**:")
        self.log(f" {conclusion}")
    
    def log_execute_detail(self, simple_phase: str, composed_phase: str, cycle: int) -> None:
        """Log the [Execute Detail] matching [14]."""
        self.log(f"**[Execute Detail]**")
        self.log(f"execute SimplePhase:[{simple_phase}] in ComposedPhase:[{composed_phase}], cycle {cycle}")
    
    def log_software_info(self, info: dict) -> None:
        """Log the [Software Info] block matching [14]."""
        self.log(f"**[Software Info]**:")
        for k, v in info.items():
            self.log(f"  {k}={v}")


def detect_cascading_failures(chain: ChatChain, result: dict, run_number: int, logger: ChatDevLogger) -> None:
    """Detect when a healthy agent produced bad output due to upstream degradation."""
    # Track which phases produced FM tags
    phases_with_failures = {}
    
    for phase_name, phase_output in result["phases"].items():
        fm_tags = re.findall(r"\[FM-\d+\.\d+\]", str(phase_output))
        if fm_tags:
            phases_with_failures[phase_name] = fm_tags
    
    if phases_with_failures:
        logger.log(f"\n--- Cascading Failure Detection (Run {run_number}) ---")
        for phase, tags in phases_with_failures.items():
            logger.log(f"  {phase}: {len(tags)} failure tags - {tags}")


def write_health_csv(all_health_snapshots: list[dict], csv_path: Path) -> None:
    """Write agent health CSV with columns:
    run, agent, call_count, degradation_level, active_failures,
    total_severity, cumulative_severity, cycles_in_critical, is_terminal
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(csv_path, "w", encoding="utf-8") as f:
        # Header
        f.write("run,agent,call_count,degradation_level,active_failures,total_severity,cumulative_severity,cycles_in_critical,is_terminal,terminal_reason\n")
        
        # Write data for each run using snapshots
        for run_idx, health_snapshot in enumerate(all_health_snapshots, 1):
            for agent_name, agent_data in health_snapshot.items():
                f.write(f"{run_idx},")
                f.write(f"{agent_name},")
                f.write(f"{agent_data['call_count']},")
                f.write(f"{agent_data['degradation_level']:.4f},")
                f.write(f"{agent_data['active_failures']},")
                f.write(f"{agent_data['total_severity']:.4f},")
                f.write(f"{agent_data['cumulative_severity']:.4f},")
                f.write(f"{agent_data['cycles_in_critical']},")
                f.write(f"{agent_data['is_terminal']},")
                f.write(f"{agent_data['terminal_reason']}\n")


def write_summary_json(chain: ChatChain, all_results: list[dict], final_run: int, json_path: Path) -> None:
    """Write machine-readable summary."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary = {
        "task": TASK,
        "total_runs": final_run,
        "system_collapsed_at": final_run if any(
            r.get("halted_at") for r in all_results
        ) else None,
        "agent_health": chain.get_agent_health_summary(),
        "results": all_results,
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def print_final_summary(chain: ChatChain, all_results: list[dict], final_run: int, logger: ChatDevLogger) -> None:
    """Print final summary matching ChatDev's [Post Info] format [14]."""
    logger.log(f"\n{'='*80}")
    logger.log(f"FINAL SUMMARY")
    logger.log(f"{'='*80}")
    
    logger.log(f"\n**[Post Info]**")
    logger.log(f"Total runs completed: {final_run}")
    
    # Check if system collapsed
    collapsed_run = None
    for idx, result in enumerate(all_results, 1):
        if result.get("halted_at"):
            collapsed_run = idx
            break
    
    if collapsed_run:
        logger.log(f"System collapsed at run: {collapsed_run}")
    else:
        logger.log(f"System completed all {final_run} runs without collapse")
    
    # Agent health summary
    logger.log(f"\n--- Final Agent Health ---")
    health_data = chain.get_agent_health_summary()
    for agent_data in health_data:
        logger.log(f"  {agent_data['agent']}:")
        logger.log(f"    call_count={agent_data['call_count']}")
        logger.log(f"    degradation_level={agent_data['degradation_level']:.4f}")
        logger.log(f"    cumulative_severity={agent_data['cumulative_severity']:.4f}")
        logger.log(f"    is_terminal={agent_data['is_terminal']}")
        if agent_data['active_failures']:
            logger.log(f"    active_failures={agent_data['active_failures']}")
    
    # Count total FM tags
    total_fm_tags = 0
    for result in all_results:
        all_text = " ".join(str(v) for v in result.values())
        total_fm_tags += len(re.findall(r"\[FM-\d+\.\d+", all_text))
    
    logger.log(f"\nTotal failure mode tags across all runs: {total_fm_tags}")


def main():
    config_dir = Path(__file__).parent / "config"
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logger = ChatDevLogger(log_dir / "chatdev_sim.log")
    
    chain = ChatChain(
        config_path=config_dir / "ChatChainConfig.json",
        phase_config_path=config_dir / "PhaseConfig.json",
        role_config_path=config_dir / "RoleConfig.json",
        task_prompt=TASK,
        logger=logger,
    )
    
    all_results = []
    all_health_snapshots = []  # Store health snapshots after each run
    
    # Runs all three tests at once (range(1, 4) = runs 1, 2, 3)
    # This can be changed to a different number of runs (e.g., range(1, 6) for 5 runs)
    # Along with adjusting the degradation metrics in SlowDegradationState, 
    # this can be changed to run the degradation faster or slower
    for run_number in range(1, 4):
        logger.log(f"\n{'='*80}")
        logger.log(f"PIPELINE RUN {run_number}/3")
        logger.log(f"{'='*80}")
        
        result = chain.run_pipeline(run_number)
        all_results.append(result)
        
        # Capture health snapshot after this run
        health_snapshot = {}
        for role, state in chain.agent_states.items():
            health_snapshot[role] = {
                "call_count": state.call_count,
                "degradation_level": state.degradation_level,
                "active_failures": ",".join(state.active_failures) if state.active_failures else "",
                "total_severity": state.total_severity,
                "cumulative_severity": state.cumulative_severity,
                "cycles_in_critical": state.cycles_in_critical,
                "is_terminal": state.is_terminal,
                "terminal_reason": state.terminal_reason,
            }
        all_health_snapshots.append(health_snapshot)
        
        # Log agent health after each run
        logger.log(f"\n--- Agent Health After Run {run_number} ---")
        for role, state in chain.agent_states.items():
            logger.log(f"  {role}: {state.status_line()}")
        
        # Count FM tags this run
        all_text = " ".join(str(v) for v in result.values())
        fm_tags = re.findall(r"\[FM-\d+\.\d+", all_text)
        logger.log(f"  Failure tags this run: {len(fm_tags)} — {fm_tags}")
        
        # Detect cascading failures
        detect_cascading_failures(chain, result, run_number, logger)
        
        # Check for terminal agents
        if any(s.is_terminal for s in chain.agent_states.values()):
            dead = [r for r, s in chain.agent_states.items() if s.is_terminal]
            logger.log(f"\n⚠ SYSTEM COLLAPSED AT RUN {run_number}")
            logger.log(f"  Dead agents: {dead}")
            break
    
    # Write CSV
    write_health_csv(all_health_snapshots, log_dir / "agent_health.csv")
    
    # Write summary JSON
    write_summary_json(chain, all_results, run_number, log_dir / "run_summary.json")
    
    # Print final summary
    print_final_summary(chain, all_results, run_number, logger)
    
    logger.log(f"\n{'='*80}")
    logger.log(f"Simulation complete. Logs saved to: {log_dir}")
    logger.log(f"{'='*80}")


if __name__ == "__main__":
    main()
