# MetaGPT Simulator Changelog

## Version 1.1.0 - Early Termination Feature

### Early Termination Behavior
- Added mid-pipeline termination: System halts immediately when an agent dies after their phase
- Added run-level termination: System skips remaining runs if any agent is terminal after a complete run
- Prevents wasted computation on already-degraded systems
- Logs collapse run number in final summary and CSV output
- Updated README with "Early Termination Behavior" section explaining both termination modes
- Added example of agent death in README showing terminal state and halt message

### Documentation Updates
- Added early termination to Overview section as a key feature
- Updated "Running the Simulator" section to clarify termination condition (any agent, not all)
- Updated "Expected Behavior" section to note that system may collapse before run 4
- Added detailed explanation of termination conditions and behavior
- Added example log output showing agent death and pipeline halt
- Updated CSV output format documentation to include terminal_reason column

### Configuration
- No configuration changes required - early termination is automatic based on agent terminal state
- Collapse run number tracked and reported in logs and summaries

## Version 1.0.0 - Initial Implementation

### Architecture
- Created faithful MetaGPT simulator with publish-subscribe message pool architecture
- Implemented MessagePool class with publish/subscribe pattern
- Implemented Message dataclass for document-based communication
- Created 5-agent pipeline with symmetric degradation:
  - Product Manager (Action: WritePRD)
  - Architect (Action: WriteDesign)
  - Project Manager (Action: WriteTasks)
  - Engineer (Action: WriteCode)
  - QA Engineer (Action: WriteTest)
- No cycles or back-and-forth - linear document-based pipeline
- Created main entry point: `run_metagpt_sim.py`

### Degradation Model
- Integrated with existing `degrading_brain.py` for MAST failure injection
- Used `SlowDegradationState` with INCREMENT=0.25 (faster than ChatDev's 0.015)
- Symmetric degradation: all agents called once per run
- Full degradation arc across 4 runs:
  - Run 1: All agents at level 0.25
  - Run 2: All agents at level 0.50
  - Run 3: All agents at level 0.75
  - Run 4: All agents at level 1.00 (all failure modes unlocked)

### Output Files
- `metagpt_sim.log`: Full log with Action tags and degradation tracking
- `metagpt_health.csv`: Agent health per run (same format as ChatDev)
- `metagpt_messages.json`: All messages from message pool

### Key Differences from ChatDev
- Document-based architecture vs conversation-based
- Symmetric degradation vs asymmetric (Programmer degrades fastest in ChatDev)
- Cascading failures through documents vs conversations
- No paired conversations or review cycles
- Message pool for publish-subscribe pattern

### Configuration
- Environment variables via `.env` file (Anthropic, OpenAI)
- Configurable number of runs (NUM_RUNS = 4)
- Configurable degradation increment (DEGRADATION_INCREMENT = 0.25)

### Environment Setup
- Ensured `load_dotenv()` called before any agent imports
- Added metagpt directory to Python path for brain imports
- Configured for Anthropic and OpenAI providers

### Output Files
- `logs/metagpt_sim.log`: Full log with Action tags and degradation tracking
- `logs/metagpt_health.csv`: Per-run agent health tracking
- `logs/metagpt_messages.json`: All messages from message pool

### Known Limitations
- Degradation rates calibrated for 3-run execution
- Call counts may vary slightly based on LLM response patterns
- System may collapse before run 3 if fatal failures trigger early

### Future Improvements
- Add configurable run count
- Implement degradation rate tuning
- Add more detailed failure mode analytics
- Support for additional ChatDev phases
