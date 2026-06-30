"""MetaGPT-Faithful Calculator Degradation Simulator.

Uses a publish-subscribe message pool architecture where each agent
produces a structured document. Agents subscribe to other agents' output
types. Each agent executes exactly ONCE per run with symmetric degradation.

Output: MetaGPT-format logs showing [FM-X.X] tags appearing and
multiplying across runs, with cascading failures visible through
document corruption.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add metagpt directory to path for brain imports
metagpt_dir = Path(__file__).parent
sys.path.insert(0, str(metagpt_dir))

load_dotenv()

# Import from metagpt (not metagpt.agents)
from degrading_brain import SlowDegradationState, degrading_think

TASK = (
    "Build a simple Python calculator that supports addition, "
    "subtraction, multiplication, and division. It should run in "
    "the terminal, prompt the user for two numbers and an operation, "
    "handle division by zero, and loop until the user types quit."
)

# Configurable number of runs
NUM_RUNS = 4

# Degradation increment (higher than ChatDev's 0.015 because agents get fewer calls)
DEGRADATION_INCREMENT = 0.25


# ---------------------------------------------------------------------------
# Message Pool Architecture
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A message in the MetaGPT message pool."""
    role: str           # who sent it
    action: str         # what action produced it
    content: str        # the document content
    run_number: int     # which run this message belongs to


class MessagePool:
    """Simple message pool for publish-subscribe pattern."""
    
    def __init__(self):
        self.messages: list[Message] = []
    
    def publish(self, message: Message) -> None:
        """Publish a message to the pool."""
        self.messages.append(message)
    
    def get_by_role(self, role: str) -> list[Message]:
        """Get all messages from a specific role."""
        return [m for m in self.messages if m.role == role]
    
    def get_latest_by_action(self, action: str) -> Message | None:
        """Get the most recent message with a specific action."""
        for m in reversed(self.messages):
            if m.action == action:
                return m
        return None
    
    def get_by_run(self, run_number: int) -> list[Message]:
        """Get all messages from a specific run."""
        return [m for m in self.messages if m.run_number == run_number]
    
    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class MetaGPTLogger:
    """Simple logger for MetaGPT simulation."""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("")
    
    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp} {level}] {message}"
        # Always write to file (UTF-8 supports all characters)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
        # Try to print to console, skip if encoding fails
        try:
            print(formatted)
        except UnicodeEncodeError:
            # Skip console output for this message if encoding fails
            pass


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
                f.write(f"\"{agent_data['active_failures']}\",")
                f.write(f"{agent_data['total_severity']:.4f},")
                f.write(f"{agent_data['cumulative_severity']:.4f},")
                f.write(f"{agent_data['cycles_in_critical']},")
                f.write(f"{agent_data['is_terminal']},")
                f.write(f"\"{agent_data['terminal_reason']}\"\n")


def print_final_summary(all_results: list[dict], agent_states: dict, logger: MetaGPTLogger, collapse_run: int | None = None) -> None:
    """Print final summary."""
    logger.log(f"\n{'='*80}")
    logger.log(f"FINAL SUMMARY")
    logger.log(f"{'='*80}")
    
    if collapse_run:
        logger.log(f"\nSystem collapsed at run: {collapse_run}")
    else:
        logger.log(f"\nSystem completed all {NUM_RUNS} runs without collapse")
    
    logger.log(f"\nTotal runs completed: {len(all_results)}")
    
    # Check if any agent is terminal
    terminal_agents = {name: state for name, state in agent_states.items() if state.is_terminal}
    if terminal_agents:
        logger.log(f"\nTerminal agents:")
        for name, state in terminal_agents.items():
            logger.log(f"  {name}: {state.terminal_reason}")
    else:
        logger.log(f"\nNo terminal agents - all completed successfully")
    
    # Agent health summary
    logger.log(f"\n--- Final Agent Health ---")
    for name, state in agent_states.items():
        logger.log(f"  {name}:")
        logger.log(f"    call_count={state.call_count}")
        logger.log(f"    degradation_level={state.degradation_level:.4f}")
        logger.log(f"    cumulative_severity={state.cumulative_severity:.4f}")
        logger.log(f"    is_terminal={state.is_terminal}")
        if state.active_failures:
            logger.log(f"    active_failures={state.active_failures}")


def run_metagpt_pipeline(run_number: int, agent_states: dict, logger: MetaGPTLogger, message_pool: MessagePool) -> None:
    """Run one MetaGPT pipeline iteration using message pool.
    
    Pipeline (NO cycles, NO back-and-forth, NO paired conversations):
      Each agent executes ONCE, publishes to message pool, downstream agents subscribe.
    """
    logger.log(f"\n{'='*80}")
    logger.log(f"**[Pipeline Run {run_number}/{NUM_RUNS}]**")
    logger.log(f"{'='*80}")
    
    # Phase 1: Product Manager → WritePRD
    logger.log(f"\n**[Action: WritePRD]** — Product Manager")
    pm_state = agent_states["Product Manager"]
    pm_system = (
        "You are a Product Manager. Write a Product Requirements Document (PRD) "
        "for the given task. Include:\n"
        "1. Product Goals (3 bullet points)\n"
        "2. User Stories (3 user stories)\n"
        "3. Requirements (numbered list of functional requirements)\n"
        "4. Constraints and Limitations\n"
        "Output in structured markdown format."
    )
    prd_output = degrading_think(pm_system, f"Task: {TASK}", pm_state, max_tokens=800)
    prd_message = Message(role="Product Manager", action="WritePRD", content=prd_output, run_number=run_number)
    message_pool.publish(prd_message)
    logger.log(f"Product Manager published WritePRD:")
    logger.log(prd_output)
    
    # Check if Product Manager is terminal
    if pm_state.is_terminal:
        logger.log(f"Pipeline halted: Product Manager is dead. Reason: {pm_state.terminal_reason}")
        return
    
    # Phase 2: Architect → WriteDesign
    logger.log(f"\n**[Action: WriteDesign]** — Architect")
    logger.log(f"Architect subscribes to: WritePRD")
    arch_state = agent_states["Architect"]
    arch_system = (
        "You are a Software Architect. Based on the PRD, write a System Design document. "
        "Include:\n"
        "1. Architecture Overview\n"
        "2. File Structure (list all files needed)\n"
        "3. Class/Function Definitions (name, purpose, inputs, outputs)\n"
        "4. Data Flow\n"
        "Output in structured markdown format."
    )
    prd_content = message_pool.get_latest_by_action("WritePRD").content
    design_output = degrading_think(arch_system, f"PRD:\n{prd_content}", arch_state, max_tokens=800)
    design_message = Message(role="Architect", action="WriteDesign", content=design_output, run_number=run_number)
    message_pool.publish(design_message)
    logger.log(f"Architect published WriteDesign:")
    logger.log(design_output)
    
    # Check if Architect is terminal
    if arch_state.is_terminal:
        logger.log(f"Pipeline halted: Architect is dead. Reason: {arch_state.terminal_reason}")
        return
    
    # Phase 3: Project Manager → WriteTasks
    logger.log(f"\n**[Action: WriteTasks]** — Project Manager")
    logger.log(f"Project Manager subscribes to: WriteDesign")
    pmgr_state = agent_states["Project Manager"]
    pmgr_system = (
        "You are a Project Manager. Based on the system design, break it into "
        "implementation tasks. Include:\n"
        "1. Task List (numbered, with acceptance criteria)\n"
        "2. Dependencies between tasks\n"
        "3. Priority order\n"
        "Output in structured markdown format."
    )
    design_content = message_pool.get_latest_by_action("WriteDesign").content
    tasks_output = degrading_think(pmgr_system, f"System Design:\n{design_content}", pmgr_state, max_tokens=800)
    tasks_message = Message(role="Project Manager", action="WriteTasks", content=tasks_output, run_number=run_number)
    message_pool.publish(tasks_message)
    logger.log(f"Project Manager published WriteTasks:")
    logger.log(tasks_output)
    
    # Check if Project Manager is terminal
    if pmgr_state.is_terminal:
        logger.log(f"Pipeline halted: Project Manager is dead. Reason: {pmgr_state.terminal_reason}")
        return
    
    # Phase 4: Engineer → WriteCode
    logger.log(f"\n**[Action: WriteCode]** — Engineer")
    logger.log(f"Engineer subscribes to: WriteTasks AND WriteDesign")
    eng_state = agent_states["Engineer"]
    eng_system = (
        "You are a Software Engineer. Based on the task list and system design, "
        "implement the complete Python code. Output ONLY valid Python code in a single code block."
    )
    tasks_content = message_pool.get_latest_by_action("WriteTasks").content
    design_content = message_pool.get_latest_by_action("WriteDesign").content
    code_input = f"Tasks:\n{tasks_content}\n\nDesign:\n{design_content}"
    code_output = degrading_think(eng_system, code_input, eng_state, max_tokens=2000)
    code_message = Message(role="Engineer", action="WriteCode", content=code_output, run_number=run_number)
    message_pool.publish(code_message)
    logger.log(f"Engineer published WriteCode:")
    logger.log(code_output)
    
    # Check if Engineer is terminal
    if eng_state.is_terminal:
        logger.log(f"Pipeline halted: Engineer is dead. Reason: {eng_state.terminal_reason}")
        return
    
    # Phase 5: QA Engineer → WriteTest
    logger.log(f"\n**[Action: WriteTest]** — QA Engineer")
    logger.log(f"QA Engineer subscribes to: WriteCode AND WritePRD")
    qa_state = agent_states["QA Engineer"]
    qa_system = (
        "You are a QA Engineer. Review the code against the original PRD. "
        "Check: does it compile, does it meet requirements, are there bugs, "
        "does it handle edge cases. End with verdict: PASS or FAIL with explanation."
    )
    prd_content = message_pool.get_latest_by_action("WritePRD").content
    code_content = message_pool.get_latest_by_action("WriteCode").content
    qa_input = f"PRD:\n{prd_content}\n\nCode:\n{code_content}"
    qa_output = degrading_think(qa_system, qa_input, qa_state, max_tokens=800)
    qa_message = Message(role="QA Engineer", action="WriteTest", content=qa_output, run_number=run_number)
    message_pool.publish(qa_message)
    logger.log(f"QA Engineer published WriteTest:")
    logger.log(qa_output)
    
    # Check if QA Engineer is terminal
    if qa_state.is_terminal:
        logger.log(f"Pipeline halted: QA Engineer is dead. Reason: {qa_state.terminal_reason}")
        return


def capture_health_snapshot(agent_states: dict) -> dict:
    """Capture current health state of all agents."""
    snapshot = {}
    for name, state in agent_states.items():
        snapshot[name] = {
            "call_count": state.call_count,
            "degradation_level": state.degradation_level,
            "active_failures": state.active_failures,
            "total_severity": state.total_severity,
            "cumulative_severity": state.cumulative_severity,
            "cycles_in_critical": state.cycles_in_critical,
            "is_terminal": state.is_terminal,
            "terminal_reason": state.terminal_reason,
        }
    return snapshot


def write_messages_json(message_pool: MessagePool, json_path: Path) -> None:
    """Write all messages from message pool to JSON file."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    messages_data = []
    for msg in message_pool.messages:
        messages_data.append({
            "role": msg.role,
            "action": msg.action,
            "content": msg.content,
            "run_number": msg.run_number
        })
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, indent=2)


def main():
    """Main entry point."""
    # Setup paths
    script_dir = Path(__file__).parent
    log_path = script_dir / "logs" / "metagpt_sim.log"
    csv_path = script_dir / "logs" / "metagpt_health.csv"
    json_path = script_dir / "logs" / "metagpt_messages.json"
    
    # Initialize logger
    logger = MetaGPTLogger(log_path)
    logger.log("="*80)
    logger.log("MetaGPT Calculator Degradation Simulator")
    logger.log("="*80)
    logger.log(f"Task: {TASK}")
    logger.log(f"Number of runs: {NUM_RUNS}")
    logger.log(f"Degradation increment: {DEGRADATION_INCREMENT}")
    
    # Initialize message pool
    message_pool = MessagePool()
    
    # Initialize agent states (persist across runs)
    # Use custom degradation increment
    agent_states = {
        "Product Manager": SlowDegradationState(),
        "Architect": SlowDegradationState(),
        "Project Manager": SlowDegradationState(),
        "Engineer": SlowDegradationState(),
        "QA Engineer": SlowDegradationState(),
    }
    
    # Set degradation increment for all agents
    for state in agent_states.values():
        state.INCREMENT = DEGRADATION_INCREMENT
    
    # Run pipeline
    all_health_snapshots = []
    collapse_run = None
    
    for run_num in range(1, NUM_RUNS + 1):
        # Capture health before run
        health_snapshot = capture_health_snapshot(agent_states)
        all_health_snapshots.append(health_snapshot)
        
        # Run pipeline with message pool
        run_metagpt_pipeline(run_num, agent_states, logger, message_pool)
        
        # Log agent health after run
        logger.log(f"\n--- Agent Health After Run {run_num} ---")
        for name, state in agent_states.items():
            logger.log(f"  {name}: {state.status_line()}")
        
        # Check if any agent is terminal - stop all future runs
        if any(state.is_terminal for state in agent_states.values()):
            collapse_run = run_num
            logger.log(f"\nSYSTEM COLLAPSED AT RUN {run_num}")
            break
    
    # Capture final health
    final_health = capture_health_snapshot(agent_states)
    all_health_snapshots.append(final_health)
    
    # Write outputs
    write_health_csv(all_health_snapshots, csv_path)
    write_messages_json(message_pool, json_path)
    print_final_summary([], agent_states, logger, collapse_run)
    
    logger.log(f"\nLog file: {log_path}")
    logger.log(f"Health CSV: {csv_path}")
    logger.log(f"Messages JSON: {json_path}")


if __name__ == "__main__":
    main()
