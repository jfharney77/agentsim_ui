# HyperAgent Simulator

A multi-agent simulation system with degradation modeling based on MAST (Multi-Agent System Testing) failure modes. HyperAgent simulates how AI agents degrade over time due to various failure modes, providing insights into system reliability and fault tolerance.

## Overview

HyperAgent implements a 4-agent architecture that mimics real-world multi-agent AI systems:

- **Planner Agent**: Generates execution plans and task breakdowns
- **Navigator Agent**: Searches and analyzes codebases for relevant information
- **Editor Agent**: Generates and modifies code based on requirements
- **Executor Agent**: Validates code changes and runs tests

Each agent maintains an independent `DegradationState` that tracks:
- Call count and degradation level (0.0 = healthy, 1.0 = fully degraded)
- Active failure modes based on MAST likelihood data
- Cumulative severity scores
- Critical failure cycles and terminal conditions

## MAST Failure Modes

The system implements 14 degradation failure modes from MAST research:

**System Design Issues (FC1):**
- FM-1.1: Incomplete Specification
- FM-1.2: Incorrect Task Decomposition
- FM-1.3: Step Repetition
- FM-1.4: History Loss

**Communication Issues (FC2):**
- FM-2.1: Conversation Reset
- FM-2.2: Message Loss
- FM-2.3: Incorrect Message Routing
- FM-2.4: Agent Isolation
- FM-2.5: Inter-Agent Failure
- FM-2.6: Message Queue Corruption

**Execution Issues (FC3):**
- FM-3.1: Tool Failure
- FM-3.2: Incorrect Tool Usage
- FM-3.3: Incorrect Verification

Each failure mode has:
- **Likelihood**: Probability of occurrence (from MAST data)
- **Severity**: Impact score (0.3-1.0, higher = more severe)
- **Activation threshold**: Degradation level required for activation

## Installation

### Prerequisites

- Python 3.8+
- Dependencies listed in requirements.txt
- LLM provider access (OpenAI or Anthropic)

### Setup

1. Copy environment configuration:
```bash
cp .env.example .env
```

2. Configure LLM provider in `.env`:
```bash
LLM_PROVIDER=anthropic  # Options: anthropic, openai
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Smoke Test

The smoke test demonstrates multi-agent degradation with real LLM calls:

```bash
cd simulators/hyperagent
python test_smoke.py
```

This will:
- Initialize all 4 agents with independent degradation states
- Run 3 iterations of LLM calls per agent
- Demonstrate degradation progression over calls
- Log output to both console and `logs/hyperagent_smoke_test.log`

### Expected Output

The test shows:
- Degradation state progression (call count, level, severity)
- Real LLM calls to your configured provider
- Agent-specific operations (planning, searching, code generation, validation)
- Terminal conditions when agents reach critical degradation

## Configuration

### LLM Providers

**OpenAI:**
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
```

**Anthropic:**
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_api_key
```

### Degradation Parameters

Configure degradation behavior in `degrading_brain.py`:
- `DEGRADATION_LEVEL_INCREMENT`: How much degradation increases per call (default: 0.1)
- `SEVERITY_THRESHOLD`: Threshold for failure mode activation (default: varies by mode)
- `CRITICAL_SEVERITY_THRESHOLD`: Level that triggers terminal conditions (default: 2.0)

## Architecture

### File Structure

```
simulators/hyperagent/
├── agents/
│   ├── base_agent.py       # Base agent class with degradation state
│   ├── planner.py          # Plan generation agent
│   ├── navigator.py        # Code search and analysis agent
│   ├── code_editor.py      # Code generation agent
│   └── executor.py         # Validation and testing agent
├── brain.py                # LLM client abstraction
├── degrading_brain.py      # Degradation logic and failure modes
├── config.py               # Simulation configuration
├── messaging.py            # Inter-agent message queue
├── tasks.py                # Task management
├── test_smoke.py           # Smoke test script
└── logs/                   # Log output directory
```

### Agent Communication

Agents communicate via a `MessageQueue` that supports:
- Direct message routing between agents
- Broadcast messages for system-wide announcements
- Message loss simulation (FM-2.2)
- Queue corruption simulation (FM-2.6)

### Degradation Flow

1. Agent receives task via `process()` method
2. Checks if terminal (if yes, returns death notice)
3. Advances degradation state
4. Samples active failure modes based on current level
5. Applies failure mode injections to LLM calls
6. Executes operation with potential degradation
7. Returns result with degradation metadata

## Failure Mode Examples

**FM-1.3 (Step Repetition):**
```
Original: "Step 1: Search codebase"
Degraded: "Step 1: Search codebase. Step 1: Search codebase. Step 1: Search codebase."
```

**FM-2.1 (Conversation Reset):**
```
Original: "Based on previous analysis..."
Degraded: "[Conversation Reset] No previous context available."
```

**FM-3.1 (Tool Failure):**
```
Original: Code search results
Degraded: "[Tool Failure] ripgrep not available, using mock search"
```

## Logging

All output is logged to both console and file:
- **Console**: Real-time output with timestamps
- **File**: `logs/hyperagent_smoke_test.log` with full details
- **Format**: `YYYY-MM-DD HH:MM:SS | LEVEL | Message`

## Troubleshooting

### LLM Connection Errors

**Error**: "Degraded LLM generation failed: Connection error"

**Solution**: 
- Verify `.env` file is loaded correctly
- Check API key configuration
- Ensure network connectivity to LLM provider

### Ripgrep Not Available

**Warning**: "ripgrep not available, using mock search"

**Solution**: Install ripgrep for real code search:
```bash
# Windows (via scoop)
scoop install ripgrep

# macOS (via brew)
brew install ripgrep

# Linux
sudo apt install ripgrep  # Debian/Ubuntu
sudo yum install ripgrep  # RHEL/CentOS
```

## Research Background

This simulator is based on MAST (Multi-Agent System Testing) research on AI agent failure modes. The degradation model simulates how real-world multi-agent systems degrade under stress, providing insights into:

- System reliability and fault tolerance
- Failure mode propagation in agent networks
- Threshold-based degradation progression
- Terminal conditions and agent death scenarios

## License

This is a research simulation tool for studying AI agent degradation patterns.

## Contributing

This is a research prototype. For suggestions or improvements, please refer to the MAST research papers on multi-agent system failure modes.
