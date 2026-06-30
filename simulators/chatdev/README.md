# ChatDev Faithful Degradation Simulator

A faithful replication of ChatDev's actual architecture with MAST degradation taxonomy injection. This simulator demonstrates how agent performance degrades over successive calls through a multi-phase software development pipeline.

## Overview

This simulator implements ChatDev's exact pipeline architecture:
- **Phase-based execution**: DemandAnalysis → LanguageChoose → Coding → CodeReview → Test
- **Role-playing conversations**: Each phase is a conversation between specific roles (CEO ↔ CPO, CTO ↔ Programmer, etc.)
- **Composed phases**: CodeReview and Test cycle through sub-phases up to 3 times
- **Configuration-driven**: Uses JSON configs matching ChatDev's actual structure
- **MAST degradation**: Failure modes from the MAST taxonomy (arxiv.org/abs/2503.13657) are injected via `degrading_brain.py`
- **Slow degradation**: Custom `SlowDegradationState` ensures agents survive across multiple runs with realistic degradation rates

## Task

The simulator builds a simple Python calculator:
- Supports addition, subtraction, multiplication, and division
- Terminal interface with user prompts
- Handles division by zero
- Loops until user types "quit"

## Architecture

```
simulators/chatdev/
├── agents/                         # Existing - do not modify
│   ├── __init__.py
│   ├── brain.py
│   └── degrading_brain.py
├── config/                         # ChatDev configuration files
│   ├── ChatChainConfig.json        # Pipeline config (phases, cycles, roles)
│   ├── PhaseConfig.json            # Phase prompts (role pairs, instructions)
│   └── RoleConfig.json             # Role prompts (CEO, CPO, CTO, etc.)
├── engine/                         # Pipeline implementation
│   ├── __init__.py
│   ├── chat_chain.py               # Pipeline orchestrator with SlowDegradationState
│   ├── phase.py                    # Phase execution (Simple + Composed)
│   └── role_playing.py             # Paired agent conversation
├── logs/                           # Created at runtime
│   ├── chatdev_sim.log             # Full log matching ChatDev format
│   ├── agent_health.csv            # Degradation tracking per run
│   └── run_summary.json            # Machine-readable summary
├── run_chatdev_sim.py              # Main entry point
├── chatdev_sim.py                  # Existing - do not modify
└── README.md                       # This file
```

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHATDEV PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐
    │  Start Task     │
    │  (Calculator)   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ DemandAnalysis  │  CEO ↔ CPO (2 turns)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ LanguageChoose  │  CEO ↔ CTO (2 turns)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │     Coding      │  CTO → Programmer (1 turn)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   CodeReview    │  Reviewer ↔ Programmer (up to 3 cycles)
    │  ┌───────────┐  │
    │  │ Comment   │  │  Reviewer identifies issues
    │  │ Modify    │  │  Programmer fixes issues
    │  └───────────┘  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │      Test       │  Tester ↔ Programmer (up to 3 cycles)
    │  ┌───────────┐  │
    │  │ Error     │  │  Tester reports bugs
    │  │ Modify    │  │  Programmer fixes bugs
    │  └───────────┘  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  Final Code     │
    └─────────────────┘
```

1. **DemandAnalysis** (CEO ↔ CPO, 2 turns)
   - Decide product modality (Application, Website, etc.)
   - Output: `<INFO> Application`

2. **LanguageChoose** (CEO ↔ CTO, 2 turns)
   - Choose programming language
   - Output: `<INFO> Python`

3. **Coding** (CTO → Programmer, 1 turn)
   - Generate initial code
   - Output: Full Python source code

4. **CodeReview** (Reviewer ↔ Programmer, up to 3 cycles)
   - CodeReviewComment: Reviewer identifies issues
   - CodeReviewModification: Programmer fixes issues
   - Cycle breaks when `<INFO> Finished`

5. **Test** (Tester ↔ Programmer, up to 3 cycles)
   - TestErrorSummary: Tester reports bugs
   - TestModification: Programmer fixes bugs
   - Cycle breaks when `<INFO> Finished`

## Degradation Model

Each agent has a `SlowDegradationState` that persists across all 3 runs:

- **call_count**: Increments each time the agent participates in a conversation
- **degradation_level**: Ramps from 0.0 (healthy) to 1.0 (fully degraded) with INCREMENT=0.015
- **active_failures**: List of MAST failure modes that activated this turn
- **cumulative_severity**: Running total of severity scores across all calls
- **cycles_in_critical**: How many calls spent above critical threshold (0.8)
- **is_terminal**: True when agent is considered dead (fatal failure or cumulative severity ceiling)

### SlowDegradationState

The simulator uses a custom `SlowDegradationState` class that overrides the base `DegradationState.advance()` method with a smaller increment (0.015 instead of 0.1). This ensures agents survive across multiple runs while still showing realistic degradation patterns.

### Programmer Degrades Fastest

In the ChatDev pipeline, the Programmer gets called most often:
- Coding: 1 call (as assistant)
- CodeReviewComment: 1 call (as user)
- CodeReviewModification: 3 calls (as assistant, one per cycle)
- TestErrorSummary: 3 calls (as assistant, one per cycle)
- TestModification: 3 calls (as assistant, one per cycle)
- **Total: ~11 calls per run**

Other agents get fewer calls per run, creating realistic asymmetric degradation:
- CEO: ~3 calls (DemandAnalysis, LanguageChoose)
- CPO: ~1 call (DemandAnalysis)
- CTO: ~2 calls (LanguageChoose, Coding)
- Code Reviewer: ~3 calls (CodeReviewComment cycles)
- Software Test Engineer: ~6 calls (Test phases)

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

## Log Format

The simulator produces logs matching ChatDev's actual format [14]:

```
[2025-01-07 10:00:00 INFO] **[Preprocessing]**
**ChatDev Starts** (run 1/3)
**task_prompt**: Build a simple Python calculator...

[2025-01-07 10:00:00 INFO] System: **[chatting]**
| Parameter | Value |
| --- | --- |
| **task_prompt** | Build a simple Python calculator... |
| **assistant_role_name** | Chief Product Officer |
| **user_role_name** | Chief Executive Officer |
| **phase_name** | DemandAnalysis |

[2025-01-07 10:00:00 INFO] Chief Executive Officer: **[Start Chat]**
[ChatDev is a software company... You are Chief Product Officer...]
As the Chief Product Officer, to satisfy the new user's demand...

  [DEGRADATION] call=1 level=0.1 active=0 severity=0.00 failures=none

[2025-01-07 10:00:01 INFO] Chief Product Officer: **Chief Product Officer<->Chief Executive Officer on : DemandAnalysis, turn 0**
[ChatDev is a software company... You are Chief Executive Officer...]
For a calculator application, I recommend the Application modality...
<INFO> Application

  [DEGRADATION] call=1 level=0.1 active=0 severity=0.00 failures=none

[2025-01-07 10:00:01 INFO] **[Seminar Conclusion]**:
<INFO> Application
```

### Example of Agent Failure

When an agent degrades and a failure mode activates, it appears in the log as:

```
[2025-01-07 10:00:05 INFO] Programmer: **Programmer<->Code Reviewer on : CodeReviewComment, turn 1**

[FM-2.5: Ignored Other Agent's Input — review feedback disregarded]

The code is perfect as written. I don't see any issues that need fixing.
The reviewer's comments about missing error handling are not relevant.

  [DEGRADATION] call=8 level=0.4 active=1 severity=0.40 failures=FM-2.5
```

This shows:
- **Failure mode tag**: `[FM-2.5: Ignored Other Agent's Input]` with a brief description
- **Degraded behavior**: Agent ignores the reviewer's feedback instead of addressing it
- **Degradation status**: Shows call count, degradation level, active failures, and severity score

Multiple failures can appear together:

```
[FM-1.1: Task Specification Disobedience — constraints ignored]
[FM-2.3: Task Derailment — went off-topic]

Instead of fixing the division by zero bug, I'll add a feature to
calculate square roots and implement a graph plotting library.

  [DEGRADATION] call=12 level=0.6 active=2 severity=1.50 failures=FM-1.1,FM-2.3
```

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
cd simulators/chatdev
python run_chatdev_sim.py
```

The simulator will:
1. Run the ChatDev pipeline 3 times
2. Log all conversations to `logs/chatdev_sim.log`
3. Track agent health in `logs/agent_health.csv`
4. Write a summary to `logs/run_summary.json`
5. Stop early if any agent becomes terminal

## Output Files

### chatdev_sim.log
Full log in ChatDev format showing:
- All agent conversations with role prompts
- Degradation status after each turn
- Phase transitions and seminar conclusions
- Failure mode tags appearing over time

### agent_health.csv
CSV with columns:
- run: Run number (1-3)
- agent: Role name (CEO, CPO, CTO, Programmer, Code Reviewer, Software Test Engineer)
- call_count: Total calls for this agent
- degradation_level: Current degradation (0.0-1.0)
- active_failures: Comma-separated list of active failure modes
- total_severity: Severity score for this run
- cumulative_severity: Lifetime cumulative severity
- cycles_in_critical: Calls spent above critical threshold
- is_terminal: Whether agent is dead
- terminal_reason: Reason for termination

### run_summary.json
Machine-readable summary with:
- Task description
- Total runs completed
- Whether system collapsed and at which run
- Final agent health for all roles
- Per-run results

## Expected Behavior

1. **Run 1**: All agents healthy, clean calculator code produced
2. **Run 2**: Programmer (highest call count ~11) starts showing [FM-] tags
3. **Run 3**: Programmer failures cascade to Reviewer/Tester, possible system collapse

Each agent's call count after run 1 should be approximately:
  CEO:              ~3 calls
  CPO:              ~1 call
  CTO:              ~2 calls
  Programmer:       ~11 calls (highest - degrades fastest)
  Code Reviewer:    ~3 calls
  Software Test Engineer: ~6 calls

The Programmer degrades fastest due to highest call count, leading to:
- Buggy code in Coding phase
- Poor fixes in CodeReviewModification
- Incomplete fixes in TestModification

## References

- ChatDev paper: "ChatDev: Communicative Agents for Software Development"
- ChatDev config structure: [15] in the paper
- ChatDev log format: [14] in the paper
- MAST taxonomy: "MAST: A Taxonomy of Multi-Agent System Failures" (arxiv.org/abs/2503.13657)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history and bug fixes.
