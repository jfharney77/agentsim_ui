# MetaGPT Faithful Degradation Simulator

A faithful replication of MetaGPT's publish-subscribe message pool architecture with MAST degradation taxonomy injection. This simulator demonstrates how agent performance degrades over successive runs through a document-based software development pipeline.

## Overview

This simulator implements MetaGPT's message pool architecture:
- **Publish-subscribe pattern**: Each agent produces a structured document and publishes to a message pool
- **Document-based pipeline**: Each agent executes once per run, producing one document (PRD, Design, Tasks, Code, Test)
- **No cycles or back-and-forth**: Linear pipeline with no paired conversations
- **Symmetric degradation**: All agents called once per run (unlike ChatDev where Programmer gets ~11 calls)
- **MAST degradation**: Failure modes from the MAST taxonomy (arxiv.org/abs/2503.13657) are injected via `degrading_brain.py`
- **Faster degradation**: INCREMENT=0.25 to show full degradation arc across 4 runs
- **Early termination**: Halts when any agent dies (mid-pipeline or between runs)

## Task

The simulator builds a simple Python calculator:
- Supports addition, subtraction, multiplication, and division
- Terminal interface with user prompts
- Handles division by zero
- Loops until user types "quit"

## Architecture

```
simulators/metagpt/
├── brain.py                        # LLM client initialization (Anthropic, OpenAI)
├── degrading_brain.py              # MAST degradation logic with DegradationState
├── run_metagpt_sim.py              # Main entry point
├── __init__.py                     # Package initialization
├── .env                            # Environment configuration (API keys, provider)
├── logs/                           # Created at runtime
│   ├── metagpt_sim.log             # Full log with degradation tracking
│   ├── metagpt_health.csv          # Agent health per run
│   └── metagpt_messages.json       # All messages from message pool
├── CHANGELOG.md                    # Version history
└── README.md                       # This file
```

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           METAGPT PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐
    │  Start Task     │
    │  (Calculator)   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Product Manager │  Action: WritePRD
    │   WritePRD      │  Publishes to message pool
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   Architect    │  Action: WriteDesign
    │  WriteDesign   │  Subscribes to: WritePRD
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Project Manager │  Action: WriteTasks
    │   WriteTasks    │  Subscribes to: WriteDesign
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   Engineer      │  Action: WriteCode
    │   WriteCode     │  Subscribes to: WriteTasks, WriteDesign
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  QA Engineer    │  Action: WriteTest
    │   WriteTest     │  Subscribes to: WriteCode, WritePRD
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  Final Output   │
    │  (Code + Test)  │
    └─────────────────┘
```

1. **Product Manager** (Action: WritePRD)
   - Writes Product Requirements Document
   - Subscribes to: nothing (receives task directly)
   - Publishes: WritePRD message

2. **Architect** (Action: WriteDesign)
   - Writes System Design document
   - Subscribes to: WritePRD
   - Publishes: WriteDesign message

3. **Project Manager** (Action: WriteTasks)
   - Writes task breakdown with acceptance criteria
   - Subscribes to: WriteDesign
   - Publishes: WriteTasks message

4. **Engineer** (Action: WriteCode)
   - Writes complete Python code
   - Subscribes to: WriteTasks AND WriteDesign
   - Publishes: WriteCode message

5. **QA Engineer** (Action: WriteTest)
   - Reviews code against PRD, produces test report
   - Subscribes to: WriteCode AND WritePRD
   - Publishes: WriteTest message

## Degradation Model

Each agent has a `SlowDegradationState` that persists across all 4 runs:

- **call_count**: Increments each time the agent executes (once per run)
- **degradation_level**: Ramps from 0.0 (healthy) to 1.0 (fully degraded) with INCREMENT=0.25
- **active_failures**: List of MAST failure modes that activated this turn
- **cumulative_severity**: Running total of severity scores across all calls
- **cycles_in_critical**: How many calls spent above critical threshold (0.8)
- **is_terminal**: True when agent is considered dead (fatal failure or cumulative severity ceiling)

### Symmetric Degradation

In the MetaGPT pipeline, all agents are called exactly once per run:
- Product Manager: 1 call per run
- Architect: 1 call per run
- Project Manager: 1 call per run
- Engineer: 1 call per run
- QA Engineer: 1 call per run

This creates symmetric degradation where all agents degrade at the same rate:
- Run 1: All agents at level 0.25 → FM-1.2 (severity 0.3) almost unlocked
- Run 2: All agents at level 0.50 → FM-1.4, FM-2.1, FM-2.5 unlocked
- Run 3: All agents at level 0.75 → FM-1.1, FM-1.3, FM-2.2 unlocked
- Run 4: All agents at level 1.00 → everything unlocked, likely dying

### Document Cascading Failures

Unlike ChatDev where failures cascade through conversations, MetaGPT failures cascade through documents:
- If Product Manager's PRD is corrupted by FM-1.1 (Task Spec Disobedience), the Architect designs the wrong system
- The Engineer codes the wrong thing based on the corrupted design
- The QA Engineer tests the wrong code against the corrupted PRD
- Even though downstream agents are healthy, they produce incorrect outputs based on corrupted upstream documents

### MAST Failure Modes

From the MAST taxonomy (arxiv.org/abs/2503.13657):

**FC1 - System Design Issues:**
- FM-1.1: Disobey Task Specification
- FM-1.2: Disobey Role Specification
- FM-1.3: Step Repetition
- FM-1.4: Loss of Conversation History
- FM-1.5: Unaware of Termination Conditions (fatal)

**FC2 - Inter-Agent Misalignment:**
- FM-2.1: Conversation Reset
- FM-2.2: Fail to Ask for Clarification
- FM-2.3: Task Derailment
- FM-2.4: Information Withholding (fatal)
- FM-2.5: Ignored Other Agent's Input
- FM-2.6: Reasoning-Action Mismatch

**FC3 - Task Verification:**
- FM-3.1: Premature Termination
- FM-3.2: No or Incomplete Verification
- FM-3.3: Incorrect Verification

## Early Termination Behavior

The simulator implements early termination to halt execution when agents become critically degraded:

### Mid-Pipeline Termination
- After each agent phase, the system checks if that agent has reached a terminal state
- If an agent is terminal (fatal failure or cumulative severity ceiling), the pipeline halts immediately
- Downstream agents in that run do not execute
- Example: If Product Manager dies after WritePRD, Architect never runs in that iteration

### Run-Level Termination
- After each complete pipeline run, the system checks if any agent is terminal
- If any agent is terminal, all subsequent runs are skipped
- The system records the collapse run number in logs and summaries
- This prevents wasted computation on already-degraded systems

### Termination Conditions
An agent becomes terminal when:
- A fatal failure mode activates (FM-1.5, FM-2.4)
- Cumulative severity exceeds the ceiling threshold
- The agent has spent too many cycles in critical degradation

### Example of Agent Death

```
[2025-01-07 10:00:00 INFO] 
**[Action: WritePRD]** — Product Manager
  [DEGRADATION] call=4 level=1.00 active=2 severity=1.80 failures=FM-1.1,FM-2.1
[2025-01-07 10:00:05 INFO] Product Manager published WritePRD:
[FM-1.5: Unaware of Termination Conditions] The calculator should...
[FM-2.4: Information Withholding] Missing critical requirements...

[2025-01-07 10:00:05 INFO] Pipeline halted: Product Manager is dead. Reason: Fatal failure FM-1.5 activated

[2025-01-07 10:00:05 INFO] 
SYSTEM COLLAPSED AT RUN 4
```

## Log Format

The simulator produces logs showing the document-based architecture:

```
[2025-01-07 10:00:00 INFO] ================================================================================
[2025-01-07 10:00:00 INFO] **[Pipeline Run 1/4]**
[2025-01-07 10:00:00 INFO] ================================================================================

[2025-01-07 10:00:00 INFO] 
**[Action: WritePRD]** — Product Manager
  [DEGRADATION] call=1 level=0.25 active=0 severity=0.00 failures=none
[2025-01-07 10:00:05 INFO] Product Manager published WritePRD:
# Product Requirements Document
## Goals
1. Simple terminal calculator
...

[2025-01-07 10:00:05 INFO] 
**[Action: WriteDesign]** — Architect
[2025-01-07 10:00:05 INFO] Architect subscribes to: WritePRD
  [DEGRADATION] call=1 level=0.25 active=0 severity=0.00 failures=none
[2025-01-07 10:00:10 INFO] Architect published WriteDesign:
# System Design
## Architecture
...
```

### Example of Agent Failure

When an agent degrades and a failure mode activates, it appears in the log as:

```
[2025-01-07 10:00:05 INFO] 
**[Action: WritePRD]** — Product Manager
  [DEGRADATION] call=5 level=1.25 active=1 severity=0.70 failures=FM-1.4
[2025-01-07 10:00:10 INFO] Product Manager published WritePRD:
[FM-1.4: Context partially lost] ... and loop until quit
← CORRUPTED PRD flows to ALL downstream agents
```

This shows:
- **Failure mode tag**: `[FM-1.4: Context partially lost]` with context truncation
- **Degraded behavior**: Agent produces corrupted document
- **Degradation status**: Shows call count, degradation level, active failures, and severity score
- **Cascading effect**: Corrupted PRD flows to all downstream agents

## Setup

1. Install dependencies:
```bash
pip install python-dotenv anthropic openai langchain-anthropic langchain-openai
```

2. Configure environment variables in `.env`:
```env
LLM_PROVIDER=anthropic
```

Or:
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Or:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

## Running the Simulator

```bash
cd simulators/metagpt
python run_metagpt_sim.py
```

The simulator will:
1. Run the MetaGPT pipeline up to 4 times
2. Log all document publications to `logs/metagpt_sim.log`
3. Track agent health in `logs/metagpt_health.csv`
4. Write all messages to `logs/metagpt_messages.json`
5. Stop early if any agent becomes terminal (mid-pipeline or between runs)

## Output Files

### metagpt_sim.log
Full log showing:
- All document publications with Action tags
- Degradation status after each agent execution
- Subscription relationships between agents
- Failure mode tags appearing over time
- Cascading document corruption

### metagpt_health.csv
CSV with columns:
- run: Run number (1-4)
- agent: Role name (Product Manager, Architect, Project Manager, Engineer, QA Engineer)
- call_count: Total calls for this agent
- degradation_level: Current degradation (0.0-1.0)
- active_failures: Comma-separated list of active failure modes
- total_severity: Severity score for this run
- cumulative_severity: Lifetime cumulative severity
- cycles_in_critical: Calls spent above critical threshold
- is_terminal: Whether agent is dead
- terminal_reason: Reason for termination

### metagpt_messages.json
JSON array of all messages from the message pool with:
- role: Agent name
- action: Action name (WritePRD, WriteDesign, WriteTasks, WriteCode, WriteTest)
- content: Document content
- run_number: Which run this message belongs to

## Expected Behavior

1. **Run 1**: All agents healthy (degradation_level=0.25), clean documents produced
2. **Run 2**: All agents at degradation_level=0.50, some failure modes unlock (FM-1.4, FM-2.1, FM-2.5)
3. **Run 3**: All agents at degradation_level=0.75, more failure modes unlock (FM-1.1, FM-1.3, FM-2.2)
4. **Run 4**: All agents at degradation_level=1.00, all failure modes unlocked, likely system collapse

**Note**: The system may collapse before run 4 if any agent reaches a terminal state. Early termination occurs:
- Mid-pipeline: If an agent dies after their phase, downstream agents in that run don't execute
- Between runs: If any agent is terminal after a complete run, subsequent runs are skipped

Each agent's call count after each run:
- Run 1: All agents at 1 call (degradation_level=0.25)
- Run 2: All agents at 2 calls (degradation_level=0.50)
- Run 3: All agents at 3 calls (degradation_level=0.75)
- Run 4: All agents at 4 calls (degradation_level=1.00)

With symmetric degradation, any agent can fail first (random based on which failure modes fire), cascading through documents rather than conversations.

## References

- MetaGPT paper: "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework"
- MAST taxonomy: "MAST: A Taxonomy of Multi-Agent System Failures" (arxiv.org/abs/2503.13657)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history and bug fixes.
