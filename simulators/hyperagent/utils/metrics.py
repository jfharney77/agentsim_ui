"""
Metrics collection for HyperAgent simulation.

Tracks and reports performance metrics for the multi-agent system.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import time


@dataclass
class AgentMetrics:
    """Metrics for a single agent."""
    agent_name: str
    tasks_processed: int = 0
    total_processing_time: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    average_processing_time: float = 0.0
    
    def update(self, processing_time: float, success: bool):
        """Update metrics with a new task result."""
        self.tasks_processed += 1
        self.total_processing_time += processing_time
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.average_processing_time = self.total_processing_time / self.tasks_processed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "agent_name": self.agent_name,
            "tasks_processed": self.tasks_processed,
            "total_processing_time": self.total_processing_time,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "average_processing_time": self.average_processing_time,
            "success_rate": self.success_count / max(self.tasks_processed, 1)
        }


@dataclass
class StepMetrics:
    """Metrics for a single step in the simulation."""
    step_name: str
    agent: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "pending"
    error: Optional[str] = None
    
    def duration(self) -> float:
        """Get step duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


@dataclass
class SimulationMetrics:
    """
    Overall metrics for the HyperAgent simulation.
    """
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    agent_metrics: Dict[str, AgentMetrics] = field(default_factory=dict)
    steps: List[StepMetrics] = field(default_factory=list)
    current_step: Optional[StepMetrics] = None
    
    def start_run(self):
        """Start the simulation run."""
        self.start_time = datetime.now()
        self.steps.clear()
    
    def end_run(self):
        """End the simulation run."""
        self.end_time = datetime.now()
    
    def start_step(self, step_name: str, agent: str):
        """Start a new step."""
        self.current_step = StepMetrics(step_name=step_name, agent=agent, start_time=datetime.now())
        self.steps.append(self.current_step)
    
    def end_step(self, status: str = "completed", error: Optional[str] = None):
        """End the current step."""
        if self.current_step:
            self.current_step.end_time = datetime.now()
            self.current_step.status = status
            self.current_step.error = error
            self.current_step = None
    
    def summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        duration = 0.0
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        
        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.completed_tasks / max(self.total_tasks, 1),
            "steps": [
                {
                    "step_name": step.step_name,
                    "agent": step.agent,
                    "duration": step.duration(),
                    "status": step.status,
                    "error": step.error
                }
                for step in self.steps
            ],
            "agent_metrics": {
                name: metrics.to_dict() 
                for name, metrics in self.agent_metrics.items()
            }
        }
    
    def print_summary(self):
        """Print a summary of the metrics."""
        summary = self.summary()
        print("\n" + "="*50)
        print("HyperAgent Simulation Metrics Summary")
        print("="*50)
        print(f"Duration: {summary['duration_seconds']:.2f}s")
        print(f"Total Tasks: {summary['total_tasks']}")
        print(f"Completed: {summary['completed_tasks']}")
        print(f"Failed: {summary['failed_tasks']}")
        print(f"Success Rate: {summary['success_rate']:.2%}")
        print("\nSteps:")
        for step in summary['steps']:
            print(f"  {step['step_name']} ({step['agent']}): {step['status']} - {step['duration']:.2f}s")
        print("\nAgent Metrics:")
        for agent_name, metrics in summary['agent_metrics'].items():
            print(f"  {agent_name}:")
            print(f"    Tasks: {metrics['tasks_processed']}")
            print(f"    Avg Time: {metrics['average_processing_time']:.2f}s")
            print(f"    Success Rate: {metrics['success_rate']:.2%}")
        print("="*50 + "\n")
