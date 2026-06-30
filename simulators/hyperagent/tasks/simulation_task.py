"""
Simulation task for HyperAgent.

Represents a software engineering task to be solved by the multi-agent system.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


@dataclass
class SimulationTask:
    """
    Represents a software engineering task for the HyperAgent simulation.
    
    Tasks can include:
    - GitHub issue resolution
    - Repository-level code generation
    - Fault localization
    - Program repair
    """
    
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = "general"  # general, issue_resolution, code_generation, fault_localization, program_repair
    prompt: str = ""
    repo_url: str = ""
    commit: str = "main"
    language: str = "python"
    
    # Task metadata
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, in_progress, completed, failed
    priority: str = "medium"  # low, medium, high
    
    # Task context
    context: Dict[str, Any] = field(default_factory=dict)
    requirements: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    
    # Results
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Agent assignments
    assigned_agents: List[str] = field(default_factory=list)
    current_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "repo_url": self.repo_url,
            "commit": self.commit,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "priority": self.priority,
            "context": self.context,
            "requirements": self.requirements,
            "constraints": self.constraints,
            "result": self.result,
            "error_message": self.error_message,
            "execution_history": self.execution_history,
            "assigned_agents": self.assigned_agents,
            "current_agent": self.current_agent,
        }
    
    def update_status(self, status: str):
        """Update task status."""
        self.status = status
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "event": "status_change",
            "status": status
        })
    
    def assign_agent(self, agent_name: str):
        """Assign an agent to work on this task."""
        if agent_name not in self.assigned_agents:
            self.assigned_agents.append(agent_name)
        self.current_agent = agent_name
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "event": "agent_assigned",
            "agent": agent_name
        })
    
    def add_result(self, agent_name: str, result: Dict[str, Any]):
        """Add a result from an agent."""
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "event": "agent_result",
            "agent": agent_name,
            "result": result
        })
    
    def set_error(self, error_message: str):
        """Set error message and mark task as failed."""
        self.error_message = error_message
        self.update_status("failed")
    
    def complete(self, result: Dict[str, Any]):
        """Mark task as completed with result."""
        self.result = result
        self.update_status("completed")
