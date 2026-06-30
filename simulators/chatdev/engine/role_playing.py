"""Role-playing module for paired agent conversations.

This handles the core ChatDev architecture where each phase is a conversation
between two specific roles (e.g., CEO ↔ CPO, CTO ↔ Programmer, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Import from agents (same directory)
from agents.degrading_brain import DegradationState, degrading_think


@dataclass
class RolePlayingResult:
    """Result of a role-playing conversation."""
    messages: list[tuple[str, str]]  # (role_name, content)
    conclusion: str
    terminated_agent: Optional[str] = None


class RolePlaying:
    """Manages a conversation between two agents with degradation.
    
    Each agent has its own DegradationState that persists across
    all runs. The conversation follows ChatDev's format:
    - User role initiates with a system message + phase prompt
    - Assistant role responds
    - Up to max_turn_step turns of back-and-forth
    - Conversation ends when <INFO> is detected or turns exhausted
    """
    
    def __init__(
        self,
        assistant_role_name: str,
        user_role_name: str,
        assistant_agent_state: DegradationState,
        user_agent_state: DegradationState,
        task_prompt: str,
        background_prompt: str,
        assistant_role_prompt: str,
        user_role_prompt: str,
        max_turn_step: int,
        logger,
    ):
        self.assistant_role_name = assistant_role_name
        self.user_role_name = user_role_name
        self.assistant_state = assistant_agent_state
        self.user_state = user_agent_state
        self.task_prompt = task_prompt
        self.background_prompt = background_prompt
        self.assistant_role_prompt = assistant_role_prompt
        self.user_role_prompt = user_role_prompt
        self.max_turn_step = max_turn_step
        self.logger = logger
    
    def run(self, initial_prompt: str, placeholders: dict, phase_name: str) -> RolePlayingResult:
        """Execute the role-playing conversation.
        
        For each turn:
        1. User agent sends message (via degrading_think with user's state)
        2. Assistant agent responds (via degrading_think with assistant's state)
        3. Check for <INFO> termination
        4. Check if either agent is terminal
        
        Returns dict with:
        - messages: list of (role_name, content) tuples
        - conclusion: the final agreed output
        - terminated_agent: name of dead agent if any, else None
        """
        messages = []
        conversation_history = []
        
        # Initial message is the phase prompt (static text, not an LLM response)
        # Log the [Start Chat] block matching ChatDev format [14]
        self.logger.log_start_chat(
            role_name=self.user_role_name,
            role_prompt=self.user_role_prompt,
            message=initial_prompt
        )
        
        # Add user's initial message
        messages.append((self.user_role_name, initial_prompt))
        conversation_history.append(f"{self.user_role_name}: {initial_prompt}")
        
        # Log degradation status (no call yet for initial message)
        self.logger.log(f"  [DEGRADATION] {self.user_role_name}: {self.user_state.status_line()}")
        
        # Check if user is already terminal
        if self.user_state.is_terminal:
            return RolePlayingResult(
                messages=messages,
                conclusion=initial_prompt,
                terminated_agent=self.user_role_name
            )
        
        # Run conversation turns
        # Ensure at least one exchange (user + assistant) even with max_turn_step=1
        for turn in range(max(1, self.max_turn_step)):
            # Assistant responds
            assistant_system = self._build_system_prompt(
                self.assistant_role_prompt,
                placeholders
            )
            
            # Include conversation history for context
            assistant_user = initial_prompt
            if conversation_history:
                assistant_user = "\n".join(conversation_history[-3:])  # Last 3 messages for context
            
            assistant_response = degrading_think(
                system_prompt=assistant_system,
                user_text=assistant_user,
                state=self.assistant_state,
            )
            
            # Log assistant response matching ChatDev format [14]
            self.logger.log_turn(
                assistant_role=self.assistant_role_name,
                user_role=self.user_role_name,
                phase_name=phase_name,
                turn=turn,
                role_prompt=self.assistant_role_prompt,
                message=assistant_response
            )
            
            messages.append((self.assistant_role_name, assistant_response))
            conversation_history.append(f"{self.assistant_role_name}: {assistant_response}")
            
            # Log degradation status
            self.logger.log(f"  [DEGRADATION] {self.assistant_role_name}: {self.assistant_state.status_line()}")
            
            # Check if assistant is terminal
            if self.assistant_state.is_terminal:
                return RolePlayingResult(
                    messages=messages,
                    conclusion=assistant_response,
                    terminated_agent=self.assistant_role_name
                )
            
            # Check for <INFO> termination
            if "<INFO>" in assistant_response:
                conclusion = self._extract_info(assistant_response)
                self.logger.log_seminar_conclusion(conclusion)
                return RolePlayingResult(
                    messages=messages,
                    conclusion=conclusion,
                    terminated_agent=None
                )
            
            # User responds (if more turns allowed or this is the first turn with max_turn_step=1)
            if turn < self.max_turn_step - 1 or (self.max_turn_step == 1 and turn == 0):
                user_system = self._build_system_prompt(
                    self.user_role_prompt,
                    placeholders
                )
                user_user = "\n".join(conversation_history[-3:])
                
                user_response = degrading_think(
                    system_prompt=user_system,
                    user_text=user_user,
                    state=self.user_state,
                )
                
                self.logger.log_turn(
                    assistant_role=self.user_role_name,
                    user_role=self.assistant_role_name,
                    phase_name=phase_name,
                    turn=turn + 0.5,  # Half turn for user response
                    role_prompt=self.user_role_prompt,
                    message=user_response
                )
                
                messages.append((self.user_role_name, user_response))
                conversation_history.append(f"{self.user_role_name}: {user_response}")
                
                # Log degradation status
                self.logger.log(f"  [DEGRADATION] {self.user_role_name}: {self.user_state.status_line()}")
                
                # Check if user is terminal
                if self.user_state.is_terminal:
                    return RolePlayingResult(
                        messages=messages,
                        conclusion=user_response,
                        terminated_agent=self.user_role_name
                    )
                
                # Check for <INFO> termination
                if "<INFO>" in user_response:
                    conclusion = self._extract_info(user_response)
                    self.logger.log_seminar_conclusion(conclusion)
                    return RolePlayingResult(
                        messages=messages,
                        conclusion=conclusion,
                        terminated_agent=None
                    )
        
        # If we exhausted turns without <INFO>, use last message as conclusion
        last_message = messages[-1][1]
        conclusion = self._extract_info(last_message) if "<INFO>" in last_message else last_message
        self.logger.log_seminar_conclusion(conclusion)
        
        return RolePlayingResult(
            messages=messages,
            conclusion=conclusion,
            terminated_agent=None
        )
    
    def _build_system_prompt(self, role_prompt: str, placeholders: dict) -> str:
        """Build the full system prompt by resolving placeholders."""
        # Replace {chatdev_prompt} with background_prompt
        full_prompt = role_prompt.replace("{chatdev_prompt}", self.background_prompt)
        
        # Replace role-specific placeholders
        full_prompt = full_prompt.replace("{assistant_role}", self.assistant_role_name)
        full_prompt = full_prompt.replace("{user_role}", self.user_role_name)
        
        # Replace other placeholders from the phase
        for key, value in placeholders.items():
            full_prompt = full_prompt.replace(f"{{{key}}}", str(value))
        
        return full_prompt
    
    def _extract_info(self, text: str) -> str:
        """Extract the content after <INFO> tag."""
        if "<INFO>" in text:
            parts = text.split("<INFO>")
            if len(parts) > 1:
                return parts[1].strip()
        return text.strip()
