"""
Base agent class for HyperAgent simulation.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from datetime import datetime

# Import DegradationState from local degrading_brain
from ..degrading_brain import DegradationState


class BaseAgent(ABC):
    """
    Base class for all HyperAgent agents.
    
    Each agent specializes in a specific aspect of the software engineering process:
    - Planner: Central decision-making unit
    - Navigator: Information retrieval specialist
    - Editor: Code modification and generation
    - Executor: Solution validation and issue reproduction
    """

    def __init__(self, config, message_queue, name: str, logger: Optional[logging.Logger] = None):
        """
        Initialize the base agent.
        
        Args:
            config: AgentConfig instance with model settings
            message_queue: MessageQueue instance for inter-agent communication
            name: Name of the agent (e.g., "planner", "navigator")
            logger: Optional logger instance
        """
        self.config = config
        self.mq = message_queue
        self.name = name
        self.logger = logger or logging.getLogger(f"hyperagent.{name}")
        self.message_history = []
        self.action_log = []
        self.degradation_state = DegradationState()
        
    @abstractmethod
    def process(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a task and return results.
        
        Args:
            task: Task description and parameters
            context: Additional context from other agents
            
        Returns:
            Dictionary containing processing results
        """
        pass
    
    def _listen_and_respond(self):
        """
        Listen for messages from the message queue and respond.
        This method runs in a background thread for child agents.
        Applies degradation failure modes to inter-agent communication.
        """
        while True:  # Keep listening indefinitely
            message = self.mq.receive(self.name, timeout=None)  # Block indefinitely
            if message:
                # Message is already a dict from get_log()
                sender = message.get('sender', 'unknown')
                content = message.get('content', {})
                
                # Advance degradation state for this agent
                self.degradation_state.advance()
                self.logger.info(f"[{self.name}] {self.degradation_state.status_line()}")
                
                # Check for inter-agent failure modes
                if self.degradation_state.is_terminal:
                    self.logger.warning(f"[{self.name}] Agent is terminal, not responding")
                    return
                
                # FM-2.5: Ignored Other Agent's Input
                if "FM-2.5" in self.degradation_state.active_failures:
                    self.logger.warning(f"[{self.name}] FM-2.5: Ignoring input from {sender}")
                    # Send empty response
                    self.mq.send(self.name, sender, {
                        "agent": self.name,
                        "content": {"error": "Input ignored (degradation mode)"},
                        "status": "failed"
                    })
                    self._log_action("ignored_input", {"from": sender})
                    continue
                
                # FM-2.6: Reasoning-Action Mismatch
                if "FM-2.6" in self.degradation_state.active_failures:
                    self.logger.warning(f"[{self.name}] FM-2.6: Reasoning-Action Mismatch")
                    # Process normally but return mismatched result
                    response = self.process(content)
                    response["reasoning_action_mismatch"] = True
                    self.mq.send(self.name, sender, response)
                    self._log_action("reasoning_action_mismatch", {"from": sender})
                    continue
                
                # Normal processing
                self.logger.info(f"[{self.name}] Received message from {sender}")
                response = self.process(content)
                self.mq.send(self.name, sender, response)
                self._log_action("received_and_responded", {"from": sender})
    
    def get_log(self) -> list:
        """Get the agent's action log."""
        return self.action_log
    
    def _log_action(self, action: str, details: Optional[dict] = None):
        """Log an action to the agent's action log."""
        self.action_log.append({
            "action": action,
            "details": details or {},
            "timestamp": str(datetime.now())
        })
    
    def add_to_history(self, message: Dict[str, Any]):
        """Add a message to the agent's history."""
        self.message_history.append(message)
        
    def get_history(self) -> list:
        """Get the agent's message history."""
        return self.message_history
    
    def clear_history(self):
        """Clear the agent's message history."""
        self.message_history = []
