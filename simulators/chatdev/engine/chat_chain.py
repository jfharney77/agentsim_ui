"""Chat chain orchestrator for the full ChatDev pipeline.

This module implements the main pipeline that reads ChatChainConfig.json,
creates phases, and executes them in sequence. Manages shared state
(task, modality, language, codes) that flows between phases.
"""

from __future__ import annotations

import sys
from pathlib import Path
import json
from typing import Any, Optional
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

from agents.degrading_brain import (
    DegradationState,
    sample_active_failures,
    compute_run_severity,
    FATAL_MODES,
    CUMULATIVE_SEVERITY_CEILING,
    CRITICAL_THRESHOLD,
    MAX_CRITICAL_CYCLES,
)

from .phase import SimplePhase, ComposedPhase


class SlowDegradationState(DegradationState):
    """Slower degradation so agents survive across 10 runs."""
    INCREMENT = 0.015  # was 0.1 in base class

    def advance(self) -> None:
        """Override advance() with smaller increment."""
        if self.is_terminal:
            return
        self.call_count += 1
        self.degradation_level = min(1.0, self.call_count * self.INCREMENT)
        self.active_failures = sample_active_failures(self.degradation_level)
        self.total_severity = compute_run_severity(self.active_failures)
        self.cumulative_severity += self.total_severity

        if (self.degradation_level >= CRITICAL_THRESHOLD
                and len(self.active_failures) > 0
                and self.total_severity > 0):
            self.cycles_in_critical += 1

        fatal_hits = FATAL_MODES.intersection(self.active_failures)
        if fatal_hits:
            self.is_terminal = True
            self.terminal_reason = (
                f"FATAL failure mode(s) fired: {', '.join(fatal_hits)}. "
                f"These appear almost exclusively in failed runs (MAST slide 7)."
            )
            return

        if self.cumulative_severity >= CUMULATIVE_SEVERITY_CEILING:
            self.is_terminal = True
            self.terminal_reason = (
                f"Cumulative severity ({self.cumulative_severity:.2f}) "
                f"exceeded ceiling ({CUMULATIVE_SEVERITY_CEILING}). "
                f"Agent has accumulated too many failures to function."
            )
            return

        if self.cycles_in_critical >= MAX_CRITICAL_CYCLES:
            self.is_terminal = True
            self.terminal_reason = (
                f"Agent spent {self.cycles_in_critical} cycles in critical zone "
                f"(degradation >= {CRITICAL_THRESHOLD}). Forced termination."
            )
            return


class ChatChain:
    """Orchestrates the full ChatDev pipeline with degradation.
    
    Reads ChatChainConfig.json, creates phases, and executes them
    in sequence. Manages shared state (task, modality, language, codes)
    that flows between phases.
    """
    
    def __init__(
        self,
        config_path: Path,
        phase_config_path: Path,
        role_config_path: Path,
        task_prompt: str,
        logger,
    ):
        # Load all three JSON configs
        with open(config_path) as f:
            self.config = json.load(f)
        with open(phase_config_path) as f:
            self.phase_configs = json.load(f)
        with open(role_config_path) as f:
            self.role_config = json.load(f)
        
        self.task_prompt = task_prompt
        self.background_prompt = self.config.get("background_prompt", "")
        self.logger = logger
        
        # Create SlowDegradationState for EACH recruited role
        # These persist across ALL runs with slower degradation
        self.agent_states = {
            role: SlowDegradationState()
            for role in self.config["recruitments"]
        }
    
    def run_pipeline(self, run_number: int) -> dict[str, Any]:
        """Execute one full pipeline run.
        
        Shared placeholders that flow between phases:
        - {task}: the original task
        - {modality}: decided in DemandAnalysis
        - {language}: decided in LanguageChoose  
        - {codes}: produced in Coding, updated in CodeReview/Test
        - {comments}: produced in CodeReviewComment
        - {test_reports}: produced in TestErrorSummary
        - {error_summary}: produced in TestErrorSummary
        
        Log format matching [14]:
        [INFO] **[Preprocessing]**
        **ChatDev Starts** (timestamp)
        **task_prompt**: ...
        
        Then execute each phase in the chain.
        
        After all phases:
        [INFO] **[Software Info]**:
        num_code_files=...
        code_lines=...
        num_utterances=...
        
        Returns dict with all outputs and agent states.
        """
        # Log preprocessing matching [14]
        self.logger.log(f"**[Preprocessing]**")
        self.logger.log(f"**ChatDev Starts** (run {run_number})")
        self.logger.log(f"**task_prompt**: {self.task_prompt}")
        
        # Initialize placeholders with shared state
        placeholders = {
            "task": self.task_prompt,
            "modality": "",
            "language": "",
            "codes": "",
            "comments": "",
            "test_reports": "",
            "error_summary": "",
        }
        
        results = {
            "run_number": run_number,
            "modality": "",
            "language": "",
            "codes": "",
            "halted_at": None,
            "phases": {},
        }
        
        # Execute each phase in the chain
        for phase_entry in self.config["chain"]:
            phase_name = phase_entry["phase"]
            phase_type = phase_entry["phaseType"]
            
            self.logger.log(f"\n--- Phase: {phase_name} ({phase_type}) ---")
            
            # Create phase based on type
            if phase_type == "SimplePhase":
                phase = SimplePhase(
                    phase_name=phase_name,
                    phase_config=self.phase_configs[phase_name],
                    role_config=self.role_config,
                    agent_states=self.agent_states,
                    background_prompt=self.background_prompt,
                    task_prompt=self.task_prompt,
                    logger=self.logger,
                )
            elif phase_type == "ComposedPhase":
                phase = ComposedPhase(
                    phase_name=phase_name,
                    config=phase_entry,
                    phase_configs=self.phase_configs,
                    role_config=self.role_config,
                    agent_states=self.agent_states,
                    background_prompt=self.background_prompt,
                    task_prompt=self.task_prompt,
                    logger=self.logger,
                )
            else:
                raise ValueError(f"Unknown phase type: {phase_type}")
            
            # Execute phase
            conclusion, terminated_agent = phase.execute(placeholders)
            
            # Store result
            results["phases"][phase_name] = conclusion
            
            # Update shared placeholders
            if phase_name == "DemandAnalysis":
                results["modality"] = conclusion
                placeholders["modality"] = conclusion
            elif phase_name == "LanguageChoose":
                results["language"] = conclusion
                placeholders["language"] = conclusion
            elif phase_name == "Coding":
                results["codes"] = conclusion
                placeholders["codes"] = conclusion
            elif phase_name == "CodeReview":
                results["codes"] = placeholders["codes"]
            elif phase_name == "Test":
                results["codes"] = placeholders["codes"]
            
            # Check for terminal agent
            if terminated_agent:
                results["halted_at"] = terminated_agent
                self.logger.log(f"\n⚠ Pipeline halted: {terminated_agent} is terminal")
                break
        
        # Log software info matching [14]
        self._log_software_info(results)
        
        return results
    
    def _log_software_info(self, results: dict[str, Any]) -> None:
        """Log the [Software Info] block matching [14]."""
        self.logger.log(f"\n**[Software Info]**:")
        
        codes = results.get("codes", "")
        code_lines = len(codes.split("\n")) if codes else 0
        code_files = 1 if codes else 0
        
        self.logger.log(f"  num_code_files={code_files}")
        self.logger.log(f"  code_lines={code_lines}")
        self.logger.log(f"  num_utterances={self.logger.utterance_count}")
    
    def get_agent_health_summary(self) -> list[dict]:
        """Return health data for all agents for CSV logging."""
        health_data = []
        
        for role_name, state in self.agent_states.items():
            health_data.append({
                "agent": role_name,
                "call_count": state.call_count,
                "degradation_level": state.degradation_level,
                "active_failures": ",".join(state.active_failures) if state.active_failures else "",
                "total_severity": state.total_severity,
                "cumulative_severity": state.cumulative_severity,
                "cycles_in_critical": state.cycles_in_critical,
                "is_terminal": state.is_terminal,
                "terminal_reason": state.terminal_reason,
            })
        
        return health_data
