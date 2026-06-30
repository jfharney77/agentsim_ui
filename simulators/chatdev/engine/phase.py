"""Phase execution module for ChatDev pipeline.

Implements SimplePhase (single conversation) and ComposedPhase (cycles through
sub-phases multiple times) matching ChatDev's actual architecture.
"""

from __future__ import annotations

import sys
import re
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Import degrading_brain for type hints
from agents.degrading_brain import DegradationState

from .role_playing import RolePlaying, RolePlayingResult


def extract_code(output: str) -> str:
    """Extract Python code from markdown code blocks."""
    pattern = r"```python\n(.*?)```"
    matches = re.findall(pattern, output, re.DOTALL)
    if matches:
        return "\n\n".join(matches)
    return output  # fallback to full output if no code blocks found


class SimplePhase:
    """A single phase with one role-playing conversation.
    
    Matches ChatDev's SimplePhase. Each phase:
    1. Loads its config from PhaseConfig.json
    2. Resolves placeholders in the phase prompt ({task}, {codes}, etc.)
    3. Creates a RolePlaying session between the two configured roles
    4. Runs the conversation
    5. Returns the conclusion
    """
    
    def __init__(
        self,
        phase_name: str,
        phase_config: dict[str, Any],
        role_config: dict[str, list[str]],
        agent_states: dict[str, DegradationState],
        background_prompt: str,
        task_prompt: str,
        logger,
    ):
        self.phase_name = phase_name
        self.phase_config = phase_config
        self.role_config = role_config
        self.agent_states = agent_states
        self.background_prompt = background_prompt
        self.task_prompt = task_prompt
        self.logger = logger
        
        # Extract role names from phase config
        self.assistant_role_name = phase_config["assistant_role_name"]
        self.user_role_name = phase_config["user_role_name"]
        self.max_turn_step = phase_config.get("max_turn_step", 1)
        
        # Get role prompts
        self.assistant_role_prompt = "\n".join(
            role_config[self.assistant_role_name]
        )
        self.user_role_prompt = "\n".join(
            role_config[self.user_role_name]
        )
    
    def execute(self, placeholders: dict) -> tuple[str, Optional[str]]:
        """Execute this phase.
        
        Log in ChatDev format [14]:
        [INFO] System: **[chatting]**
        | Parameter | Value |
        | --- | --- |
        | **task_prompt** | ... |
        | **assistant_role_name** | ... |
        | **user_role_name** | ... |
        | **phase_name** | ... |
        
        Then delegate to RolePlaying.run()
        
        Returns:
            (conclusion, terminated_agent) tuple
        """
        # Log the [chatting] metadata table matching [14]
        self.logger.log_chatting(
            phase_name=self.phase_name,
            assistant_role=self.assistant_role_name,
            user_role=self.user_role_name,
            task_prompt=self.task_prompt,
            phase_prompt=self.phase_config["phase_prompt"][0] if self.phase_config["phase_prompt"] else "",
            max_turn_step=self.max_turn_step
        )
        
        # Build initial prompt from phase prompts
        initial_prompt = self._build_initial_prompt(placeholders)
        
        # Get agent states
        assistant_state = self.agent_states[self.assistant_role_name]
        user_state = self.agent_states[self.user_role_name]
        
        # Create and run role-playing
        role_playing = RolePlaying(
            assistant_role_name=self.assistant_role_name,
            user_role_name=self.user_role_name,
            assistant_agent_state=assistant_state,
            user_agent_state=user_state,
            task_prompt=self.task_prompt,
            background_prompt=self.background_prompt,
            assistant_role_prompt=self.assistant_role_prompt,
            user_role_prompt=self.user_role_prompt,
            max_turn_step=self.max_turn_step,
            logger=self.logger,
        )
        
        result = role_playing.run(
            initial_prompt=initial_prompt,
            placeholders=placeholders,
            phase_name=self.phase_name
        )
        
        return result.conclusion, result.terminated_agent
    
    def _build_initial_prompt(self, placeholders: dict) -> str:
        """Build the initial user prompt from phase prompts."""
        # Resolve placeholders in phase prompts
        resolved_prompts = []
        for prompt in self.phase_config["phase_prompt"]:
            resolved = prompt
            # Replace role-specific placeholders
            resolved = resolved.replace("{assistant_role}", self.assistant_role_name)
            resolved = resolved.replace("{user_role}", self.user_role_name)
            # Replace other placeholders
            for key, value in placeholders.items():
                resolved = resolved.replace(f"{{{key}}}", str(value))
            resolved_prompts.append(resolved)
        
        return "\n".join(resolved_prompts)


class ComposedPhase:
    """A phase that cycles through sub-phases multiple times.
    
    Matches ChatDev's ComposedPhase [15]. For example, CodeReview
    cycles through (CodeReviewComment, CodeReviewModification) up
    to cycleNum times.
    
    The cycle breaks early if the assistant responds with "<INFO> Finished".
    """
    
    def __init__(
        self,
        phase_name: str,
        config: dict[str, Any],
        phase_configs: dict[str, Any],
        role_config: dict[str, list[str]],
        agent_states: dict[str, DegradationState],
        background_prompt: str,
        task_prompt: str,
        logger,
    ):
        self.phase_name = phase_name
        self.config = config
        self.phase_configs = phase_configs
        self.role_config = role_config
        self.agent_states = agent_states
        self.background_prompt = background_prompt
        self.task_prompt = task_prompt
        self.logger = logger
        
        self.cycle_num = config.get("cycleNum", 1)
        self.composition = config.get("Composition", [])
        
        # Create SimplePhase objects for each sub-phase
        self.sub_phases = []
        for sub_phase_config in self.composition:
            sub_phase_name = sub_phase_config["phase"]
            sub_phase_full_config = phase_configs[sub_phase_name]
            
            sub_phase = SimplePhase(
                phase_name=sub_phase_name,
                phase_config=sub_phase_full_config,
                role_config=role_config,
                agent_states=agent_states,
                background_prompt=background_prompt,
                task_prompt=task_prompt,
                logger=logger,
            )
            self.sub_phases.append(sub_phase)
    
    def execute(self, placeholders: dict) -> tuple[str, Optional[str]]:
        """Execute all cycles.
        
        Log in ChatDev format [14]:
        [INFO] **[Execute Detail]**
        execute SimplePhase:[CodeReviewComment] in ComposedPhase:[CodeReview], cycle 1
        
        For each cycle:
          Run each sub-phase in Composition
          If any output contains "<INFO> Finished", break
          Update placeholders (e.g., {codes} with modified code, {comments} with review)
        
        Returns:
            (final_conclusion, terminated_agent) tuple
        """
        final_conclusion = ""
        terminated_agent = None
        
        for cycle in range(1, self.cycle_num + 1):
            for sub_phase in self.sub_phases:
                # Log execute detail matching [14]
                self.logger.log_execute_detail(
                    simple_phase=sub_phase.phase_name,
                    composed_phase=self.phase_name,
                    cycle=cycle
                )
                
                # Execute sub-phase
                conclusion, term_agent = sub_phase.execute(placeholders)
                
                if term_agent:
                    terminated_agent = term_agent
                    return conclusion, terminated_agent
                
                final_conclusion = conclusion
                
                # Update placeholders based on phase output
                self._update_placeholders(sub_phase.phase_name, conclusion, placeholders)
                
                # Check for early termination
                if "<INFO> Finished" in conclusion:
                    return final_conclusion, terminated_agent
        
        return final_conclusion, terminated_agent
    
    def _update_placeholders(self, phase_name: str, conclusion: str, placeholders: dict) -> None:
        """Update placeholders based on phase output."""
        if phase_name == "Coding":
            # Extract just the Python code from markdown blocks
            placeholders["codes"] = extract_code(conclusion)
        elif phase_name == "CodeReviewComment":
            placeholders["comments"] = conclusion
        elif phase_name == "CodeReviewModification":
            placeholders["codes"] = extract_code(conclusion)
        elif phase_name == "TestErrorSummary":
            placeholders["error_summary"] = conclusion
        elif phase_name == "TestModification":
            placeholders["codes"] = extract_code(conclusion)
