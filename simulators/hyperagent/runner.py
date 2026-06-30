"""
Simulation Runner — Orchestrates the full HyperAgent simulation.

This is the main entry point that:
  1. Initializes all agents
  2. Spins up child agent listeners in threads
  3. Runs the Planner's orchestration loop
  4. Collects results and metrics
"""

import os
import threading
import json
from typing import Any, Dict, List, Optional

from .config import SimulationConfig, AgentConfig
from .messaging.message_queue import MessageQueue
from .agents.planner import PlannerAgent
from .agents.navigator import NavigatorAgent
from .agents.code_editor import CodeEditorAgent
from .agents.executor import ExecutorAgent
from .tasks.simulation_task import SimulationTask
from .utils.logger import setup_logger, log_agent_action, log_message_event
from .utils.metrics import SimulationMetrics


class SimulationRunner:
    """
    Main runner for the HyperAgent simulation.

    Usage:
        config = SimulationConfig()
        runner = SimulationRunner(config)
        results = runner.run(SimulationTask(prompt="Fix bug in parser.py"))
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()
        self.logger = setup_logger(log_file=self.config.log_file)
        self.metrics = SimulationMetrics()

        # Shared message queue
        self.mq = MessageQueue()

        # Initialize agents
        self.planner = PlannerAgent(self.config.planner, self.mq, self.logger)
        self.navigator = NavigatorAgent(self.config.navigator, self.mq, self.logger)
        self.editor = CodeEditorAgent(self.config.editor, self.mq, self.logger)
        self.executor = ExecutorAgent(self.config.executor, self.mq, self.logger)

        self._agent_threads: List[threading.Thread] = []
        self._running = False

        # Configure provider-backed LLM clients
        self._setup_llm_clients()

        self.logger.info("HyperAgent SimulationRunner initialized")
        self.logger.info(f"  Planner  : {self.planner}")
        self.logger.info(f"  Navigator: {self.navigator}")
        self.logger.info(f"  Editor   : {self.editor}")
        self.logger.info(f"  Executor : {self.executor}")

    def _build_llm(self, model_name: str):
        provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name)
        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model_name)
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER: {provider}. Supported providers: anthropic, openai."
        )

    def _setup_llm_clients(self):
        if not self.config.enable_llm:
            self.logger.info("Provider-backed LLM integration disabled")
            return

        try:
            self.planner.set_llm_client(self._build_llm(self.config.planner.model))
            self.navigator.set_llm_client(self._build_llm(self.config.navigator.model))
            self.editor.set_llm_client(self._build_llm(self.config.editor.model))
            self.executor.set_llm_client(self._build_llm(self.config.executor.model))
            self.logger.info("LLM clients successfully injected into all agents")
        except Exception as e:
            self.logger.warning(
                f"LLM client initialization failed: {e}. Running in pure simulation mode."
            )

    def _run_child_agent_listener(self, agent):
        """
        Run a child agent's listen-and-respond loop in a background thread.
        The agent continuously waits for messages and processes them.
        """
        agent_name = agent.name
        self.logger.info(f"Starting listener thread for [{agent_name}]")
        while self._running:
            try:
                agent._listen_and_respond()
            except Exception as e:
                self.logger.error(f"[{agent_name}] Error: {e}")
                break

    def _start_child_listeners(self):
        """Spin up background threads for Navigator, Editor, and Executor."""
        self._running = True
        for agent in [self.navigator, self.editor, self.executor]:
            t = threading.Thread(
                target=self._run_child_agent_listener,
                args=(agent,),
                daemon=True,
                name=f"thread-{agent.name}",
            )
            t.start()
            self._agent_threads.append(t)

    def _stop_child_listeners(self):
        """Signal child agent threads to stop."""
        self._running = False
        # Threads are daemon threads, so they'll stop when main exits
        self._agent_threads.clear()

    def run(self, task: SimulationTask) -> Dict:
        """
        Run the full HyperAgent simulation for a single task.

        Args:
            task: A SimulationTask describing what to solve.

        Returns:
            Dict containing the full results, logs, and metrics.
        """
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Starting simulation for task: {task.task_id}")
        self.logger.info(f"Prompt: {task.prompt[:200]}")
        self.logger.info(f"{'='*60}")

        self.metrics.start_run()

        # Start child agent listeners
        self._start_child_listeners()

        try:
            # Run the Planner's orchestration loop
            self.metrics.start_step("planner_orchestration", "planner")
            planner_results = self.planner.execute(task.to_dict())
            self.metrics.end_step("completed")

        except Exception as e:
            self.logger.error(f"Simulation failed: {e}")
            self.metrics.end_step("failed", str(e))
            planner_results = {"error": str(e), "final_status": "failed"}

        finally:
            self._stop_child_listeners()
            self.metrics.end_run()

        # Compile full results
        results = {
            "task": task.to_dict(),
            "planner_results": planner_results,
            "message_log": self.mq.get_log(),
            "agent_logs": {
                "planner": self.planner.get_log(),
                "navigator": self.navigator.get_log(),
                "editor": self.editor.get_log(),
                "executor": self.executor.get_log(),
            },
            "metrics": self.metrics.summary(),
        }

        # Print summary
        self.metrics.print_summary()

        self.logger.info(f"Simulation complete. Status: {planner_results.get('final_status', 'unknown')}")

        return results

    def run_batch(self, tasks: List[SimulationTask]) -> List[Dict]:
        """Run the simulation for multiple tasks sequentially."""
        results = []
        for i, task in enumerate(tasks):
            self.logger.info(f"\n--- Task {i+1}/{len(tasks)} ---")
            # Reset queues between tasks
            self.mq.clear()
            result = self.run(task)
            results.append(result)
        return results