"""
HyperAgent - Multi-agent simulation system for software engineering tasks.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent

This simulation implements the four-agent architecture:
- Planner: Central decision-making unit
- Navigator: Information retrieval specialist
- Editor: Code modification and generation
- Executor: Solution validation and issue reproduction
"""

from .config import SimulationConfig, AgentConfig
from .runner import SimulationRunner
from .tasks import SimulationTask
from .agents import PlannerAgent, NavigatorAgent, CodeEditorAgent, ExecutorAgent, BaseAgent
from .messaging import MessageQueue, Message
from .utils import HyperAgentLogger, SimulationMetrics, AgentMetrics

__version__ = "0.1.0"
__all__ = [
    "SimulationConfig",
    "AgentConfig",
    "SimulationRunner",
    "SimulationTask",
    "PlannerAgent",
    "NavigatorAgent",
    "CodeEditorAgent",
    "ExecutorAgent",
    "BaseAgent",
    "MessageQueue",
    "Message",
    "HyperAgentLogger",
    "SimulationMetrics",
    "AgentMetrics",
]
