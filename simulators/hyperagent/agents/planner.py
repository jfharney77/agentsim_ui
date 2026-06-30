"""
Planner agent for HyperAgent simulation.

The Planner agent serves as the central decision-making unit.
It processes human task prompts, generates resolution strategies,
and coordinates child agent activities.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from typing import Dict, Any, Optional, List
import logging
from .base_agent import BaseAgent
from ..degrading_brain import degrading_think


class PlannerAgent(BaseAgent):
    """
    Planner agent - Central decision-making unit.
    
    The Planner:
    - Processes human task prompts
    - Generates resolution strategies
    - Coordinates child agent activities
    - Operates iteratively until task completion or iteration limit
    """

    def __init__(self, config, message_queue, logger: Optional[logging.Logger] = None):
        super().__init__(config, message_queue, "planner", logger)
        self.current_plan = []
        self.iteration_count = 0
        self.llm_client = None  # Will be set if LLM integration is available
        
    def set_llm_client(self, llm_client):
        """Set the LLM client for real LLM calls."""
        self.llm_client = llm_client
        
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the full orchestration loop for a task.
        
        This is the main entry point for the Planner that coordinates
        all other agents through the message queue.
        
        Args:
            task: Task dictionary with 'prompt', 'task_id', etc.
            
        Returns:
            Dictionary containing final results and status
        """
        prompt = task.get("prompt", "")
        task_id = task.get("task_id", "unknown")
        repo_url = task.get("repo_url", "")
        
        self.logger.info(f"Planner starting orchestration for task {task_id}")
        
        # Generate initial plan
        plan = self._generate_plan(prompt, task)
        self.current_plan = plan
        self._log_action("generate_plan", {"plan": plan})
        
        # Execute plan steps
        results = {}
        final_status = "completed"
        
        for step in plan:
            step_agent = step.get("agent")
            step_action = step.get("action")
            
            self.logger.info(f"Executing step: {step_agent} - {step_action}")
            
            # Send task to child agent via message queue
            self.mq.send("planner", step_agent, {
                "action": step_action,
                "task_id": task_id,
                "context": task
            })
            
            # Wait for response (with timeout)
            response = self.mq.receive("planner", timeout=60.0)
            
            if response:
                results[step_agent] = response.get("content", {})
                self._log_action(f"completed_{step_action}", {"agent": step_agent})
                
                # Check if step failed
                if response.get("content", {}).get("status") == "failed":
                    final_status = "failed"
                    break
            else:
                self.logger.warning(f"No response from {step_agent}")
                final_status = "timeout"
                break
        
        return {
            "final_status": final_status,
            "plan": plan,
            "results": results,
            "iterations": self.iteration_count
        }
    
    def process(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a task and generate a plan (legacy method for compatibility).
        
        Args:
            task: Task description with 'prompt' and 'task_id'
            context: Additional context from previous iterations
            
        Returns:
            Dictionary containing the plan and next actions
        """
        self.iteration_count += 1
        
        prompt = task.get("prompt", "")
        task_id = task.get("task_id", "unknown")
        
        self.logger.info(f"Planner processing task {task_id}, iteration {self.iteration_count}")
        
        # Generate plan (with LLM if available)
        plan = self._generate_plan(prompt, task)
        
        self.current_plan = plan
        self._log_action("generate_plan", {"iteration": self.iteration_count, "plan": plan})
        
        return {
            "agent": "planner",
            "task_id": task_id,
            "iteration": self.iteration_count,
            "plan": plan,
            "next_agent": self._determine_next_agent(plan),
            "status": "in_progress"
        }
    
    def _generate_plan(self, prompt: str, task: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Generate a plan for the task.

        Uses degrading_think for LLM calls with degradation progression.
        Falls back to template plan if LLM fails.
        """
        try:
            # Use degrading_think with degradation state
            system_prompt = f"""
You are a software engineering planner. Given the following task, generate a step-by-step plan.

Repository: {task.get('repo_url', 'N/A')}
Language: {task.get('language', 'python')}

Generate a plan with steps for the following agents:
- navigator: Search and analyze codebase
- editor: Modify code files
- executor: Validate and test changes

Return the plan as a JSON list of steps with 'step', 'agent', 'action', and 'description' fields.
"""
            user_text = f"Task: {prompt}"
            
            # Use degrading_think with degradation state
            response = degrading_think(
                system_prompt=system_prompt,
                user_text=user_text,
                state=self.degradation_state,
                max_tokens=800
            )
            
            # Parse response (simplified - in production use proper JSON parsing)
            # For now, fall back to template
            self.logger.info(f"Degraded LLM response received: {str(response)[:100]}")
        except Exception as e:
            self.logger.warning(f"Degraded LLM generation failed: {e}, using template plan")
        
        # Template plan
        plan = [
            {"step": "1", "agent": "navigator", "action": "search_codebase", "description": "Search for relevant code"},
            {"step": "2", "agent": "navigator", "action": "analyze_dependencies", "description": "Analyze dependencies"},
            {"step": "3", "agent": "editor", "action": "read_file", "description": "Read target files"},
            {"step": "4", "agent": "editor", "action": "modify_code", "description": "Modify code files"},
            {"step": "5", "agent": "executor", "action": "validate", "description": "Validate changes"},
            {"step": "6", "agent": "executor", "action": "run_tests", "description": "Run tests"},
        ]
        
        return plan
    
    def _determine_next_agent(self, plan: List[Dict[str, str]]) -> str:
        """Determine which agent should execute next based on the plan."""
        if not plan:
            return "planner"
        
        first_step = plan[0]
        return first_step.get("agent", "navigator")
    
    def update_plan(self, feedback: Dict[str, Any]):
        """Update the plan based on feedback from other agents."""
        self.logger.info(f"Planner updating plan based on feedback: {feedback}")
        self._log_action("update_plan", {"feedback": feedback})
