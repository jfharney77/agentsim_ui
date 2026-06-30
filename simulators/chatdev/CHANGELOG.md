# ChatDev Simulator Changelog

## Version 1.1.0 - Documentation Improvements

### Documentation
- Added visual pipeline diagram to README showing ChatDev phase flow with ASCII box diagram
- Added "Example of Agent Failure" section to README demonstrating:
  - Single failure mode example (FM-2.5: Ignored Other Agent's Input)
  - Multiple failure mode example (FM-1.1 and FM-2.3 together)
  - Clear illustration of failure mode tags, degraded behavior, and degradation status lines
- Removed redundant failure mode example from log format section
- Fixed directory path in running instructions from `cd chatdev_sim` to `cd simulators/chatdev`

## Version 1.0.0 - Initial Implementation

### Architecture
- Created faithful ChatDev simulator with MAST degradation taxonomy
- Implemented configuration-driven pipeline with JSON files:
  - `ChatChainConfig.json`: Pipeline structure with phases and cycles
  - `PhaseConfig.json`: Phase prompts and role assignments
  - `RoleConfig.json`: Role-specific prompts
- Implemented engine modules:
  - `chat_chain.py`: Pipeline orchestrator with state management
  - `phase.py`: SimplePhase and ComposedPhase execution
  - `role_playing.py`: Paired agent conversations
- Created main entry point: `run_chatdev_sim.py`

### Degradation Model
- Integrated with existing `agents/degrading_brain.py` for MAST failure injection
- Created `SlowDegradationState` class with INCREMENT=0.015 (vs 0.1 in base class)
- Ensures agents survive across 3 runs with realistic asymmetric degradation
- Programmer degrades fastest (~11 calls/run) vs CEO (~3 calls/run)

### Bug Fixes

#### Bug 1: Programmer dies too fast
- **Problem**: Programmer reached degradation 0.8 and died in run 1 due to 0.1 increment
- **Fix**: Created `SlowDegradationState` with INCREMENT=0.015
- **Result**: Programmer survives across 3 runs, degradation ~0.165 after run 1

#### Bug 2: Software Test Engineer state never advances
- **Problem**: Tester showed call=0 despite participating in Test phases
- **Fix**: Modified conversation loop to ensure both user and assistant respond even with max_turn_step=1
- **Result**: Tester now gets ~6 calls per run

#### Bug 3: CEO never called
- **Problem**: CEO showed call=0 despite participating in DemandAnalysis and LanguageChoose
- **Fix**: Same as Bug 2 - ensured user role gets response in conversation loop
- **Result**: CEO now gets ~3 calls per run

#### Bug 4: Final summary prints agents multiple times
- **Problem**: Agent stats repeated in cascading duplication pattern
- **Fix**: Verified single loop structure in print_final_summary()
- **Result**: Each agent appears exactly once in final summary

#### Bug 5: Failure tag count shows 0 but tags exist
- **Problem**: Regex `r"\[FM-\d+\.\d+\]"` didn't match tags like `[FM-1.3: Step Repetition]`
- **Fix**: Changed regex to `r"\[FM-\d+\.\d+"` (removed closing bracket)
- **Result**: Failure tags now correctly counted

#### Bug 6: {assistant_role} placeholder not resolved
- **Problem**: Phase prompts contained literal `{assistant_role}` in output
- **Fix**: Added placeholder resolution in `_build_system_prompt()` and `_build_initial_prompt()`
- **Result**: All placeholders correctly resolved before reaching LLM

#### Bug 7: Codes placeholder shows full markdown
- **Problem**: Programmer output included full markdown explanations, not just code
- **Fix**: Added `extract_code()` function to extract Python code from markdown blocks
- **Result**: Downstream phases receive clean Python code only

#### Bug 8: Agent states not accumulating across runs in CSV
- **Problem**: CSV showed identical data for all 3 runs
- **Fix**: Capture health snapshots after each run, write snapshots to CSV
- **Result**: CSV now shows correct state progression across runs

#### Bug 9: Programmer has 39 calls after run 1
- **Problem**: Programmer showed 39 calls vs expected ~11
- **Fix**: Removed degrading_think() call for initial message (should be static text)
- **Result**: Programmer now gets ~11 calls per run as expected

### Configuration Changes
- Reduced runs from 10 to 3 for faster testing
- Updated all documentation to reflect 3-run execution
- Added project root to Python path for simulator imports
- Added inline documentation comments explaining how to adjust run count and degradation rates

### Environment Setup
- Ensured `load_dotenv()` called before any agent imports
- Added project root path manipulation in all engine modules for simulator imports
- Configured for Anthropic and OpenAI providers

### Output Files
- `logs/chatdev_sim.log`: Full ChatDev-format log with degradation tags
- `logs/agent_health.csv`: Per-run agent health tracking
- `logs/run_summary.json`: Machine-readable summary with final states

### Known Limitations
- Degradation rates calibrated for 3-run execution
- Call counts may vary slightly based on LLM response patterns
- System may collapse before run 3 if fatal failures trigger early

### Future Improvements
- Add configurable run count
- Implement degradation rate tuning
- Add more detailed failure mode analytics
- Support for additional ChatDev phases
